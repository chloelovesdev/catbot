import configparser
import asyncio
import os
import sys
import json
import importlib
import inspect
import copy
import shlex
import traceback
import re
import time

from typing import Optional
from markdown2 import Markdown

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteMemberEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse, RoomMemberEvent,
                 crypto, exceptions, RoomSendResponse, RoomSendError)

from catbot import module

from catbot.clients import CommonClient
from catbot.events import (BotSetupEvent, ReplyBufferingEvent)
from catbot.dispatcher import (CommandDispatcher, MessageDispatcher)

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        print("Channel client woop")
        self.add_event_callback(self.cb_maybe_run_commands, RoomMessageText)

        if not self.bot_config.command_prefix:
            self.bot_config.add("command_prefix", "!")

        # find and create factoid directory
        self.factoid_dir_path = os.path.realpath(os.path.join(self.global_store_path, "factoids"))
        if not os.path.isdir(self.factoid_dir_path):
            os.mkdir(self.factoid_dir_path)

        self.command_dispatcher = CommandDispatcher(self)
        self.message_dispatcher = MessageDispatcher(self)

    def queue_text(self, body):
        self.message_dispatcher.queue.append({
            "type": "text",
            "body": body
        })

    def queue_html(self, body):
        self.message_dispatcher.queue.append({
            "type": "html",
            "body": body
        })

    def queue_markdown(self, body):
        self.message_dispatcher.queue.append({
            "type": "markdown",
            "body": body
        })

    def queue_image(self, url, body="image"):
        self.message_dispatcher.queue.append({
            "type": "image",
            "url": url,
            "body": body
        })

    def dispatcher_tasks(self):
        if not self.bot_config.concurrent_commands:
            self.bot_config.update("concurrent_commands", 5)
            self.save_config()

        tasks = []

        for x in range(self.bot_config.concurrent_commands):
            tasks.append(self.command_dispatcher.start())
        tasks.append(self.message_dispatcher.start())

        return tasks

    # currently using files as a "DB"
    def get_factoid_path(self, name):
        name = name.replace("/", "").replace(".", "").replace("\\", "")
        return os.path.join(self.factoid_dir_path, name)

    def get_factoid_content_binary(self, name):
        factoid_path = self.get_factoid_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "rb")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None
            
    def get_factoid_content(self, name):
        factoid_path = self.get_factoid_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "r")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None
        
    def set_factoid_content(self, name, content):
        factoid_path = self.get_factoid_path(name)
        factoid_file = open(factoid_path, "w")
        factoid_file.write(content)
        factoid_file.close()
        return True
        
    def set_factoid_content_binary(self, name, content):
        factoid_path = self.get_factoid_path(name)
        factoid_file = open(factoid_path, "wb")
        factoid_file.write(content)
        factoid_file.close()
        return True

    def load_modules(self):
        result = {}

        path_to_commands = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "modules"))
        print(path_to_commands)

        for fname in os.listdir(path_to_commands):
            path = os.path.join(path_to_commands, fname)
            
            if os.path.isdir(path):
                # skip directories
                continue
                
            print(f"Loading module from {path}")

            command_name = os.path.splitext(fname)[0]

            # import module's spec from file
            spec = importlib.util.spec_from_file_location("catbot.modules." + command_name, path)
            imported_module = importlib.util.module_from_spec(spec)
            # load it into python
            spec.loader.exec_module(imported_module)

            # instantiate the class with the same name as the file
            for class_name, class_obj in inspect.getmembers(imported_module, inspect.isclass):
                if class_name.lower() == command_name.lower().replace("_", "").replace("-", ""):
                    module = class_obj(self)
                    result[command_name] = module

        return result

    async def membership_changed(self, state):
        if state == "leave" or state == "ban":
            await self.delete_self()

    async def delete_self(self):
        await self.room_leave(self.bot_config.server.channel)
        print("DEACTIVATEBOT")
        sys.stderr.write("DEACTIVATEBOT\n")
        sys.stderr.flush()
        sys.exit(1)

    async def room_setup(self):
        print("Bot is now in the room and we have the user data for the room")

        # bot was just invited
        if self.bot_inviter_id:
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                print("Inviter has correct power level")
                await self.queue_text("catbot here at your service :)") #TODO: get hello from config file
            else:
                await self.send_text(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()

        self.modules = self.load_modules()
        self.commands = await self.send_to_all_modules(BotSetupEvent(), return_dicts=True)# TODO
        print(self.commands)

    async def send_to_module(self, module_obj, event, buffer_replies=True, return_dicts=False):
        results = []

        for method_name, method_obj in inspect.getmembers(module_obj, predicate=inspect.ismethod):
            # do not include any __ functions, they are module internals
            if not "__" in method_name:
                method_result = method_obj(event)

                if not method_result == None:
                    result = await method_result

                    # normally module setups returns lists of commands they handle
                    if result != None and isinstance(result, list):
                        results += result
                    # some modules return dicts in their setup handlers
                    # this is used to know which commands eat all input and do not use redirection
                    elif result != None and isinstance(result, dict) and return_dicts:# TODO
                        return result
        
        return results

    async def send_to_all_modules(self, event, buffer_replies=False, return_dicts=False):
        results = {}

        # create a buffering event
        buffering_event = ReplyBufferingEvent(self, event, buffer_replies=buffer_replies)
        
        # loop through all loaded modules
        for name, module in self.modules.items():
            results[module] = await self.send_to_module(module, buffering_event, return_dicts=return_dicts)
        
        return results

    async def cb_maybe_run_commands(self, room: MatrixRoom, event: RoomMessageText):
        # dont use anything thats not from the bot's channel,
        # or if the setup hasn't completed.
        if not self.has_setup or room.room_id != self.bot_config.server.channel:
            return
            
        # asyncio.ensure_future(self.command_dispatcher.maybe_run_commands(event))
        self.command_dispatcher.queue.append(event)
