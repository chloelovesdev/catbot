import configparser
import asyncio
import os
import sys
import json
import importlib
import inspect

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteMemberEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse, RoomMemberEvent,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

from ..modules import module
from ..events import (BotSetupEvent, CommandEvent)

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        print("Channel client woop")
        self.add_event_callback(self.cb_maybe_run_commands, RoomMessageText)

        if not self.bot_config.command_prefix:
            self.bot_config.command_prefix = "!"
        if not self.bot_config.factoid_prefix:
            self.bot_config.factoid_prefix = "?"

    def load_modules(self):
        result = {}

        path_to_commands = os.path.join(os.path.dirname(__file__), "..", "modules")
        print(path_to_commands)

        for fname in os.listdir(path_to_commands):
            path = os.path.join(path_to_commands, fname)
            print(path)
            if os.path.isdir(path):
                # skip directories
                continue
            
            command_name = os.path.splitext(fname)[0]

            spec = importlib.util.spec_from_file_location("catbot.modules." + command_name, path)
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)

            for class_name, class_obj in inspect.getmembers(foo, inspect.isclass):
                if class_name.lower() == command_name.lower().replace("_", "").replace("-", ""):
                    module = class_obj(self)
                    result[command_name] = module
                    print(module)

        return result

    async def membership_changed(self, state):
        if state == "leave" or state == "ban":
            await self.delete_self()

    async def room_setup(self):
        print("Bot is now in the room and we have the user data for the room")

        if self.bot_inviter_id:
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            #TODO: add matrix event?
            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                print("Inviter has correct power level")
                await self.send_text_to_room("catbot here at your service :)") #TODO: get hello from config file
            else:
                await self.send_text_to_room(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()

        self.modules = self.load_modules()
        await self.send_to_all_modules(BotSetupEvent())

    async def send_to_all_modules(self, event):
        for name, module in self.modules.items():
            for method_name, method_obj in inspect.getmembers(module, predicate=inspect.ismethod):
                if not method_name.startswith("__"):
                    method_result = method_obj(event)
                    if not method_result == None:
                        await method_result
#            print(classes)

    async def delete_self(self):
        await self.room_leave(self.bot_config.server.channel)
        print("DEACTIVATEBOT")
        sys.stderr.write("DEACTIVATEBOT\n")
        sys.stderr.flush()
        sys.exit(1)

    async def cb_maybe_run_commands(self, room: MatrixRoom, event: RoomMessageText):
        # dont use anything thats not from the bot's channel
        if room.room_id != self.bot_config.server.channel:
            # print(room.room_id)
            return

        if event.body.startswith(self.bot_config.command_prefix):
            await self.run_command(room, event.body)
        if event.body.startswith(self.bot_config.factoid_prefix):
            await self.run_factoid(room, event.body)

    async def run_command(self, room, message):
        msg_without_prefix = message[len(self.bot_config.command_prefix):]
        split_message = msg_without_prefix.split(" ")
        clean_cmd_name = split_message[0].replace(".", "").replace("/", "").replace("\\", "")
        msg_without_command = message[len(self.bot_config.command_prefix) + len(clean_cmd_name):].lstrip()
        await self.send_to_all_modules(CommandEvent(clean_cmd_name, msg_without_command))