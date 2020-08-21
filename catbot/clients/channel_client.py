import configparser
import asyncio
import os
import sys
import json
import importlib
import inspect
import copy
import shlex
import re

from typing import Optional
from markdown2 import Markdown

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteMemberEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse, RoomMemberEvent,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

from ..modules import module
from ..events import (BotSetupEvent, ReplyBufferingEvent)

class CommandNotFound(Exception):
    pass

class RecursionLimitExceeded(Exception):
    pass

class EmptyInput(Exception):
    pass

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        print("Channel client woop")
        self.add_event_callback(self.cb_maybe_run_commands, RoomMessageText)

        if not self.bot_config.command_prefix:
            self.bot_config.add("command_prefix", "!")
        if not self.bot_config.factoid_prefix:
            self.bot_config.add("factoid_prefix", "!")

        self.factoid_dir_path = os.path.realpath(os.path.join(self.global_store_path, "factoids"))
        if not os.path.isdir(self.factoid_dir_path):
            os.mkdir(self.factoid_dir_path)

    def get_factoid_path(self, name):
        name = name.replace("/", "").replace(".", "").replace("\\", "")
        return os.path.join(self.factoid_dir_path, name)

    def get_factoid_content(self, name):
        factoid_path = self.get_factoid_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "r")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None

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

        if self.bot_inviter_id:
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            #TODO: add matrix event?
            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                print("Inviter has correct power level")
                await self.send_text("catbot here at your service :)") #TODO: get hello from config file
            else:
                await self.send_text(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()

        self.modules = self.load_modules()
        self.commands = await self.send_to_all_modules(BotSetupEvent(), return_dicts=True)
        print(self.commands)

    async def __send_to_module(self, module_obj, event, buffer_replies=True, return_dicts=False):
        results = []

        for method_name, method_obj in inspect.getmembers(module_obj, predicate=inspect.ismethod):
            # do not include any __ functions
            if not "__" in method_name:
                method_result = method_obj(event)

                if not method_result == None:
                    result = await method_result

                    if result != None and isinstance(result, list):
                        results += result
                    elif result != None and isinstance(result, dict) and return_dicts:
                        return result
        
        return results

    async def send_to_all_modules(self, event, buffer_replies=False, return_dicts=False):
        results = {}

        # create a buffering event
        buffering_event = ReplyBufferingEvent(self, event, buffer_replies=buffer_replies)
        
        # loop through all loaded modules
        for name, module in self.modules.items():
            results[module] = await self.__send_to_module(module, buffering_event, return_dicts=return_dicts)
        
        return results
    
    def consolidate_replies(self, replies: list):
        print("Consolidating replies: " + str(replies))
        is_html = False
        reply_to_send = ""

        for reply in replies:
            if reply_to_send != "":
                reply_to_send += "\n"

            if reply['type'] == "html":
                is_html = True
                reply_to_send += reply['body']
            elif reply['type'] == "markdown":
                is_html = True
                reply_to_send += Markdown().convert(reply['body'])
            else:
                reply_to_send += reply['body']
        
        return (is_html, reply_to_send)

    def __get_factoid_path(self, name):
        name = name.replace("/", "").replace(".", "").replace("\\", "")
        return os.path.join(self.factoid_dir_path, name)

    async def run_command(self, event, recurse_count=0):
        print(f"Running command with body {event.body}")
        if recurse_count == 10:
            raise RecursionLimitExceeded()

        # take a copy and remove the prefix
        async def actually_run(event):
            print(f"Actually run {event.body}")
            results = []
            no_commands_found = True
            
            if len(event.body) == 0:
                raise EmptyInput()

            for module, commands in self.commands.items():
                for command in commands:
                    if event.body.startswith(command):
                        buffering_event = ReplyBufferingEvent(self, event, buffer_replies=True)
                        await self.__send_to_module(module, buffering_event)
                        results += buffering_event.buffer
                        no_commands_found = False
            
            if no_commands_found:
                print(f"Trying to run \"{event.body}\" as factoid")

                factoid_command_split = event.body.split(" ")

                factoid_content = self.get_factoid_content(factoid_command_split[0])
                if factoid_content == None:
                    raise CommandNotFound(event.body)

                for x in range(100):
                    if "$" + str(x) in factoid_content and len(factoid_command_split) <= x:
                        raise EmptyInput(f"More input is required for '{event.body}")

                for x in range(len(factoid_command_split)):
                    factoid_content = factoid_content.replace("$" + str(x), '"' + factoid_command_split[x].replace("\"", "\\\"") + '"')
                
                if len(factoid_command_split) > 1:
                    factoid_content = factoid_content.replace("$@", '"' + " ".join(factoid_command_split[1:]).replace("\"", "\\\"") + '"')
                elif "$@" in factoid_content:
                    raise EmptyInput(f"Input required for {event.body}")

                if factoid_content.startswith("<cmd>"):
                    print(f"Run command in factoid {factoid_content}")
                    copied_event = copy.deepcopy(event)
                    copied_event.body = factoid_content[len("<cmd>"):]
                    return await self.run_command(copied_event, recurse_count + 1)
                elif factoid_content.startswith("<html>"):
                    return [{
                        "type": "html",
                        "body": factoid_content[len("<html>"):]
                    }]
                elif factoid_content.startswith("<markdown>"):
                    return [{
                        "type": "markdown",
                        "body": factoid_content[len("<markdown>"):]
                    }]
                else:
                    for module, commands in self.commands.items():
                        for command in commands:
                            if factoid_content.startswith(f"<{command}>"):
                                copied_event = copy.deepcopy(event)
                                copied_event.body = factoid_content[len(command) + 2:]
                                copied_event.body = command + " " + copied_event.body
                                return await self.run_command(copied_event, recurse_count + 1)

                return [{
                    "type": "text",
                    "body": factoid_content
                }]

            return results

        # streamline run commands that eat everything
        print("test")
        for module, commands in self.commands.items():
            print("")
            print(module)
            print(commands)
            print("")

            if isinstance(commands, dict):
                for command, eat_everything in commands.items():
                    if event.body.startswith(command) and eat_everything:
                        buffering_event = ReplyBufferingEvent(self, event, buffer_replies=True)
                        await self.__send_to_module(module, buffering_event)
                        return buffering_event.buffer

        previous_output = []
        count = 0
        results = []

        split_by_redirect = re.split("(?<!\\\\)[|]", event.body)

        for command in split_by_redirect:
            copied_event = copy.deepcopy(event)
            copied_event.body = command.strip().replace("\\|", "|")

            if len(previous_output) > 0:
                print(f"Previous output found, old body is {copied_event.body}")
                if len(copied_event.body) > 0 and copied_event.body[-1:] != " ":
                    copied_event.body += " "
                _, consolidated_previous_output = self.consolidate_replies(previous_output)
                copied_event.body = copied_event.body + consolidated_previous_output
                print(f"Previous output found, new body is {copied_event.body}")
            
            if len(split_by_redirect) - 1 == count:
                results = await actually_run(copied_event)
                print("Results:")
                print(results)
            else:
                previous_output = await actually_run(copied_event)
                print("Setting previous_output:")
                print(previous_output)

            count = count + 1

        return results

        # shlex_instance = shlex.shlex(event.body, punctuation_chars="|", posix=True)
        # previous_output = []
        # collected_args = []

        # while True:
        #     current_token = shlex_instance.get_token()
        #     print(f"Token: {current_token}")
        #     if current_token == ";" or current_token == "|" or current_token == None:
        #         print("Attempting to run command")
        #         copied_event = copy.deepcopy(event)
        #         copied_event.body = shlex.join(collected_args)

        #         if len(previous_output) > 0:
        #             print(f"Previous output found, old body is {copied_event.body}")
        #             if len(copied_event.body) > 0 and copied_event.body[-1:] != " ":
        #                 copied_event.body += " "
        #             _, consolidated_previous_output = self.consolidate_replies(previous_output)
        #             copied_event.body = copied_event.body + consolidated_previous_output
        #             print(f"Previous output found, new body is {copied_event.body}")
        #             previous_output = []

        #         if current_token != "|":
        #             results += await actually_run(copied_event)
        #             print("Results:")
        #             print(results)
        #         else:
        #             previous_output = await actually_run(copied_event)
        #             print("Setting previous_output:")
        #             print(previous_output)

        #         collected_args = []

        #         if current_token == None:
        #             break
        #     else:
        #         collected_args.append(current_token)
        
        # return results

    async def cb_maybe_run_commands(self, room: MatrixRoom, event: RoomMessageText):
        if not self.has_setup:
            return
        
        # dont use anything thats not from the bot's channel
        if room.room_id != self.bot_config.server.channel:
            # print(room.room_id)
            return

        if event.body.startswith(self.bot_config.command_prefix):
            copied_event = copy.deepcopy(event)
            copied_event.body = copied_event.body[len(self.bot_config.command_prefix):]

            try:
                results = await self.run_command(copied_event)
                is_html, reply_to_send = self.consolidate_replies(results)
                
                if is_html:
                    await self.send_html(reply_to_send)
                else:
                    await self.send_text(reply_to_send)
            except (CommandNotFound, RecursionLimitExceeded, EmptyInput) as e:
                await self.send_text("An error occurred. " + str(e))
        else:
            await self.send_to_all_modules(event)