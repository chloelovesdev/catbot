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

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteNameEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse,
                 crypto, exceptions, RoomSendResponse)

from asyncio.exceptions import TimeoutError

from .common_client import CommonClient

from python_json_config.config_node import ConfigNode

class MainClient(CommonClient):
    def __init__(self, global_store_path, entry_point_file):
        super().__init__(global_store_path=global_store_path, bot_id="MAIN")

        self.entry_point_file = entry_point_file

        self.add_event_callback(self.cb_try_setup_bot, InviteNameEvent)

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
            print("Invited to bot's main room, joining!")
            await self.join(room.room_id)
            return

        print("Trying to set up bot, someone gave me an invite!")
        print(room)
        print(event)

        if self.check_room_with_bot_exists(room):
            await self.send_text("bot already exists with room id and invite given(?)")
            return
        else:
            loop = asyncio.get_event_loop()
            loop.create_task(self.setup_bot(None, room=room))

    def create_bot_config(self, bot_id: str, room_id: str):
        os.mkdir(os.path.join(self.global_store_path, bot_id))

        config_path = os.path.join(self.global_store_path, bot_id, "config.json")

        # give our config data
        new_bot_config = ConfigNode({})
        new_bot_config.add("server.url", self.bot_config.server.url)
        new_bot_config.add("server.user_id", self.bot_config.server.user_id)
        new_bot_config.add("server.device_name", self.bot_config.server.device_name)
        new_bot_config.add("server.channel", room_id)
        new_bot_config.add("server.password", self.bot_config.server.password)

        new_bot_config.add("owner.session_ids", None)

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
        elif bot_id == None:
            raise Exception("None bot_id but no event parameters")

        bots_as_dict = self.bot_config.bots.to_dict()
        if bots_as_dict[bot_id]['active'] == False:
            print("Not setting up bot " + bot_id + ". Bot is inactive.")
            return None

        print("Setup bot: " + bot_id)

        # read the process stdout and stderr concurrently always
        # demarcate with [BOT_ID]
        async def read_proc_output_task(proc, std, std_to_read_from, timeout):
            async def read_and_print(std, std_to_read_from):
                line = await std_to_read_from.readline()
                # line = line.decode("ascii").rstrip()
                if line:
                    print(f"[{bot_id}] [{std}] {line}")
                    if line.rstrip() == b"DEACTIVATEBOT":
                        print(f"Deleting bot on {std} with ID " + bot_id)
                        if std == "stdout":
                            self.bot_config.update(f"bots.{bot_id}.active", False) # bot is disabled
                            self.save_config()
                        return True
                    else:
                        return False
                else:
                    return False

            while True:
                is_terminated = await read_and_print(std, std_to_read_from)

                if is_terminated:
                    break

            print("read_and_print loop terminated")

        async def start_and_listen_proc():
            proc = await asyncio.create_subprocess_exec(sys.executable, "-u", self.entry_point_file, bot_id, 
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            await asyncio.gather(
                asyncio.ensure_future(read_proc_output_task(proc, "stdout", proc.stdout, 10)),
                asyncio.ensure_future(read_proc_output_task(proc, "stderr", proc.stderr, 10))
            )

        print("Before gather")
        return start_and_listen_proc()

    def check_room_with_bot_exists(self, room: MatrixRoom):
        if self.bot_config.bots:
            bots_as_dict = self.bot_config.bots.to_dict() #TODO lookup how to do this

            for bot_id in bots_as_dict:
                if bots_as_dict[bot_id]['room_id'] == room.room_id and bots_as_dict[bot_id]['active']:
                    return True

        return False

    async def room_setup(self):
        print("We are setting up!")
        await self.send_text("Hello, world!")