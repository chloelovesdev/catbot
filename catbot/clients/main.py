import configparser
import asyncio
import os
import sys
import json
import random
import string
import sys
import subprocess
import threading
import select
import logging

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteNameEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse,
                 crypto, exceptions, RoomSendResponse)

from asyncio.exceptions import TimeoutError

from catbot.clients import CommonClient

from python_json_config.config_node import ConfigNode

logger = logging.getLogger(__name__)

class MainClient(CommonClient):
    def __init__(self, global_store_path, entry_point_file):
        super().__init__(global_store_path=global_store_path, bot_id="MAIN")

        self.entry_point_file = entry_point_file
        self.add_event_callback(self.cb_try_setup_bot, InviteNameEvent)

        self.management_server = None
        self.processes = {}
        self.last_x_messages = {}

        logger.info("Main client initialized with entry point %s", self.entry_point_file)

    def setup_cached_bots(self):
        tasks = []

        if self.bot_config.bots:
            bots_as_dict = self.bot_config.bots.to_dict() #TODO lookup how to do this
            for bot_id in bots_as_dict:
                task = self.setup_bot(bot_id)
                if task:
                    tasks += [task]

        return tasks

    async def cb_try_setup_bot(self, room: MatrixRoom, event: InviteNameEvent):
        if room.room_id == self.bot_config.server.channel:
            logger.info("Main client was invited to it's room and will now try to join")
            await self.join(room.room_id)
            return

        logger.info("Invited to a channel that was not the main one. Attempting to setup bot.")

        if self.check_room_with_bot_exists(room):
            await self.send_text("bot already exists with room id and invite given(?)")
            logger.warning("User %s attempted to setup bot where it already exists at.", event.state_key)
            return
        else:
            logger.info("Creating a new task to spin up a new bot")
            loop = asyncio.get_event_loop()
            loop.create_task(self.setup_bot(None, room=room))

    def create_bot_config(self, bot_id: str, room_id: str):
        logger.info("Creating bot config for bot %s and room %s", bot_id, room_id)
        os.mkdir(os.path.join(self.global_store_path, bot_id))

        config_path = os.path.join(self.global_store_path, bot_id, "config.json")

        # give our config data
        new_bot_config = ConfigNode({})
        new_bot_config.add("server.url", self.bot_config.server.url)
        new_bot_config.add("server.user_id", self.bot_config.server.user_id)
        new_bot_config.add("server.device_name", self.bot_config.server.device_name)
        new_bot_config.add("server.channel", room_id)
        new_bot_config.add("server.password", self.bot_config.server.password)

        new_bot_config.add("trust", None)

        # dump the config's dictionary
        config_as_json = json.dumps(new_bot_config.to_dict())

        # save it to a file
        config_file = open(config_path, "w")
        config_file.write(config_as_json)
        config_file.close()

    def setup_bot(self, bot_id: str, room: MatrixRoom = None):
        if bot_id == None and not room == None:
            updated_existing_bot = False

            # if a bot with the room id exists, make it active
            if self.bot_config.bots:
                bots_as_dict = self.bot_config.bots.to_dict()
                for bot_id, bot_data in bots_as_dict.items():
                    if bot_data['room_id'] == room.room_id:
                        logger.info("A configuration already exists. Setting bot %s status to active.", bot_id)
                        self.bot_config.update(f"bots.{bot_id}.active", True)
                        self.save_config()
                        updated_existing_bot = True

            if not updated_existing_bot:
                bot_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

                self.create_bot_config(bot_id, room.room_id)

                # update the main clients bot config with the new information
                if self.bot_config.bots == None:
                    self.bot_config.add("bots", {})
                self.bot_config.add(f"bots.{bot_id}", {})
                self.bot_config.add(f"bots.{bot_id}.room_id", room.room_id)
                self.bot_config.add(f"bots.{bot_id}.active", True)
                self.save_config()

        if bot_id == None:
            logger.error("No bot ID was specified when setting up a bot")
            raise Exception("None bot_id but no event parameters")

        bots_as_dict = self.bot_config.bots.to_dict()
        if bots_as_dict[bot_id]['active'] == False:
            logger.warning("Not setting up bot %s because it is inactive", bot_id)
            return None

        logger.info("Setting up bot with ID %s", bot_id)

        # read the process stdout and stderr concurrently always
        # demarcate with [BOT_ID]
        async def read_proc_output_task(proc, std, std_to_read_from, timeout):
            async def read_and_print(std, std_to_read_from):
                line = await std_to_read_from.readline()
                # line = line.decode("ascii").rstrip()
                if line:
                    try:
                        line = line.decode("utf-8").rstrip()
                    except:
                        line = str(line)

                    print(f"[{bot_id}] {line}")
                    
                    if not bot_id in self.last_x_messages.keys():
                        self.last_x_messages[bot_id] = []

                    self.last_x_messages[bot_id].append(line)
                    if len(self.last_x_messages[bot_id]) > 30: #TODO: configurable by main bot config
                        self.last_x_messages[bot_id].pop(0)

                    if self.management_server:
                        if bot_id in self.management_server.open_sockets:
                            for ws in self.management_server.open_sockets[bot_id]:
                                await ws.send_str(line)

                    if line.rstrip() == b"DEACTIVATEBOT":
                        logger.info("Deleting bot on stream %s with ID %s", std, bot_id)
                        if std == "stdout":
                            self.bot_config.update(f"bots.{bot_id}.active", False) # bot is disabled
                            self.save_config()
                        return True
                    else:
                        return False
                else:
                    return True

            while True:
                is_terminated = await read_and_print(std, std_to_read_from)

                if is_terminated:
                    break

            logger.info("We have stopped listening to the %s stream for bot %s", std, bot_id)

        async def start_and_listen_proc():
            proc = await asyncio.create_subprocess_exec(sys.executable, "-u", self.entry_point_file, bot_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)

            self.processes[bot_id] = proc
            await asyncio.gather(
                asyncio.ensure_future(read_proc_output_task(proc, "stdout", proc.stdout, 10)),
                asyncio.ensure_future(read_proc_output_task(proc, "stderr", proc.stderr, 10))
            )
            del self.processes[bot_id]

        return start_and_listen_proc()

    def check_room_with_bot_exists(self, room: MatrixRoom):
        if self.bot_config.bots:
            bots_as_dict = self.bot_config.bots.to_dict() #TODO lookup how to do this

            for bot_id in bots_as_dict:
                if bots_as_dict[bot_id]['room_id'] == room.room_id and bots_as_dict[bot_id]['active']:
                    return True

        return False

    async def room_setup(self):
        logger.info("Main bot is setting up")
        await self.send_text("Main bot started")