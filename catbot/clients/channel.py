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
import logging

from typing import Optional
from markdown2 import Markdown

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteMemberEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse, RoomMemberEvent,
                 crypto, exceptions, RoomSendResponse, RoomSendError)

from catbot import module

from catbot.clients import CommonClient
from catbot.managers import FileBasedFactoidManager
from catbot.events import (BotSetupEvent, ReplyBufferingEvent)
from catbot.dispatcher import (CommandDispatcher, MessageDispatcher, CronDispatcher)

logger = logging.getLogger(__name__)

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        self.add_event_callback(self.cb_maybe_run_commands, RoomMessageText)

        if not self.bot_config.command_prefix:
            self.bot_config.add("command_prefix", "!")
        
        self.factoids = FileBasedFactoidManager(global_store_path)

        logger.info("Initializing dispatchers")
        self.command_dispatcher = CommandDispatcher(self)
        self.message_dispatcher = MessageDispatcher(self)
        self.cron_dispatcher = CronDispatcher(self)

        self.add_response_callback(self.cb_save_users_and_devices, SyncResponse)

    async def cb_save_users_and_devices(self, response):
        if not self.has_setup:
            return

        if self.bot_config.server.channel in self.rooms:
            output = {}

            for user in self.rooms[self.bot_config.server.channel].users:
                if user == self.bot_config.server.user_id:
                    continue

                for olm_device in self.device_store:
                    if olm_device.user_id == user:
                        if user in output:
                            output[user] += [olm_device.device_id]
                        else:
                            output[user] = [olm_device.device_id]

            path_to_output = os.path.realpath(os.path.join(self.store_path, "devices.json"))
            output_file = open(path_to_output, "w")
            output_file.write(json.dumps(output, indent=4))
            output_file.close()

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
            logger.info("Client does not have concurrent_commands set in config. Updating config with default value.")
            self.bot_config.update("concurrent_commands", 5)
            self.save_config()

        tasks = []

        for x in range(self.bot_config.concurrent_commands):
            tasks.append(self.command_dispatcher.start())
        tasks.append(self.message_dispatcher.start())
        tasks.append(self.cron_dispatcher.start())

        return tasks

    def load_modules(self):
        result = {}

        path_to_commands = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "modules"))
        logger.info("Found path to modules: %s", path_to_commands)

        for fname in os.listdir(path_to_commands):
            path = os.path.join(path_to_commands, fname)
            
            if os.path.isdir(path):
                # skip directories
                continue

            if self.bot_config.modules:
                if not fname in self.bot_config.modules:
                    logger.info("Skipping module %s, module is disabled", path)
                    continue
                
            logger.info("Loading module from %s", path)

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

        logger.info("Module loading complete.")
        return result

    async def membership_changed(self, state):
        if state == "leave" or state == "ban":
            logger.error("Bot was kicked or banned from it's room.")
            await self.delete_self()

    async def delete_self(self):
        logger.info("Deactivating bot.")

        await self.room_leave(self.bot_config.server.channel)
        print("DEACTIVATEBOT")
        sys.stderr.write("DEACTIVATEBOT\n")
        sys.stderr.flush()
        sys.exit(1)

    async def room_setup(self):
        logger.info("Bot is now in the room and we have the user data for the room")

        # bot was just invited
        if self.bot_inviter_id:
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                logger.info("Inviter has correct power level")
                self.queue_text("catbot here at your service :)") #TODO: get hello from config file
            else:
                logger.error("Bot joined but the inviter doesn't have the correct power level (>=50 required)")
                await self.send_text(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()
                raise Exception("Could not kill bot")

        self.modules = self.load_modules()
        self.commands = await self.send_to_all_modules(BotSetupEvent(), return_dicts=True)# TODO

        for module, commands in self.commands.items():
            logger.info("Commands found for module %s:", module.__class__.__name__)

            if isinstance(commands, dict):
                for command_name, eat_everything in commands.items():
                    logger.info("\t%s %s", command_name, "(eats everything)" if eat_everything else "(does not eat everything)")
            else:
                for command_name in commands:
                    logger.info("\t%s", command_name)
        
        logger.info("Bot is set up and ready.")

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
        if not self.has_setup or room.room_id != self.bot_config.server.channel or self.bot_config.server.user_id == event.sender:
            return

        if room.encrypted:
            device_id = None

            for olm_device in self.device_store:
                for key_type, key in olm_device.keys.items():
                    if key == event.sender_key:
                        device_id = olm_device.device_id
            
            if device_id == None:
                logger.error("User %s sent a message but we could not find a matching device", event.sender)
                return
            else:
                trust = self.bot_config.trust.to_dict() if self.bot_config.trust else None

                if trust != None and event.sender in trust:
                    if trust[event.sender] != None and not device_id in trust[event.sender]:
                        logger.warning("%s tried to send a message on device %s but we do not trust them.", event.sender, device_id)
                        return
                elif trust != None:
                    logger.warning("%s tried to send a message on device %s but we are not yet configured to trust them.", event.sender, device_id)
                    return

        self.command_dispatcher.queue.append(event)
