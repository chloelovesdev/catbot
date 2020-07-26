import configparser
import asyncio
import os
import sys
import json
import random
import string

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

from python_json_config.config_node import ConfigNode

class MainClient(CommonClient):
    def __init__(self, global_store_path, entry_point_file):
        super().__init__(global_store_path=global_store_path, bot_id="MAIN")

        self.entry_point_file = entry_point_file
        self.add_event_callback(self.cb_try_setup_bot, InviteEvent)

    async def setup_cached_bots(self):
        if self.bot_config.bots:
            bots_as_dict = self.bot_config.bots.to_dict() #TODO lookup how to do this
            for bot_id in bots_as_dict:
                await self.setup_bot(bot_id)

    async def cb_try_setup_bot(self, room: MatrixRoom, event: InviteEvent):
        print(room)
        print(event)

        if self.check_room_with_bot_exists(room):
            self.send_text_to_room("bot already exists with room id and invite given(?)")
            return
        else:
            await self.setup_bot(None, event=event, room=room)

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

    async def setup_bot(self, bot_id: str, room: MatrixRoom = None, event: InviteEvent = None):
        if bot_id == None and not room == None and not event == None:
            bot_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

            self.create_bot_config(bot_id, room.room_id)

            # update the main clients bot config with the new information
            if self.bot_config.bots == None:
                self.bot_config.add("bots", {})
            self.bot_config.add(f"bots.{bot_id}", {})
            self.bot_config.add(f"bots.{bot_id}.room_id", room.room_id)
            self.save_config()
        elif bot_id == None:
            raise Exception("None bot_id but no event parameters")

        print("Setup bot: " + bot_id)

        # TODO: double check bot_id is not lethal parameter
        proc = await asyncio.create_subprocess_exec(self.entry_point_file, bot_id,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE)
        print(proc)
                                    
        async def read_proc_output_task(proc, std_to_read_from, timeout):
            while True:
                try:
                    line = await asyncio.wait_for(std_to_read_from.readline(), timeout)
                except asyncio.TimeoutError:
                    break
                else:
                    if not line: # EOF
                        break
                    else: 
                        print(f"[{bot_id}] {line}")
                #proc.kill() # timeout or some criterium is not satisfied
                #break
            print("timed out?")

        await asyncio.gather(
            read_proc_output_task(proc, proc.stdout, 10),
            read_proc_output_task(proc, proc.stderr, 10)
        )
        
    def check_room_with_bot_exists(self, room: MatrixRoom):
        if self.bot_config.bots and isinstance(self.bot_config.bots, dict):
            bots_as_dict = self.bot_config.bots.to_dict() #TODO lookup how to do this

            for bot_id in bots_as_dict:
                if bots_as_dict[bot_id]['room_id'] == room.room_id:
                    return True

        return False

    def after_first_sync(self):
        self.__only_trust_devices(self.bot_config.owner.session_ids)

    def __only_trust_devices(self, device_list: Optional[str] = None) -> None:
        for olm_device in self.device_store:
            if olm_device.device_id in device_list:
                self.verify_device(olm_device)
            else:
                self.blacklist_device(olm_device)