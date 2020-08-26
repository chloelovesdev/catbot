import time
import asyncio
import copy
import re
import traceback
import logging

from catbot.events import ReplyBufferingEvent

from nio import RoomMessageText

logger = logging.getLogger(__name__)

class CommandNotFound(Exception):
    pass

class RecursionLimitExceeded(Exception):
    pass

class EmptyInput(Exception):
    pass

class CommandDispatcher:
    def __init__(self, client):
        self.client = client
        self.queue = []

    async def start(self):
        while True:
            if len(self.queue) > 0:
                event = self.queue.pop(0)
                if isinstance(event, RoomMessageText):
                    logger.info("CommandDispatcher is handling message: %s", event.body)
                    await self.maybe_run_commands(event)
                else:
                    logger.error("Unhandled event %s", event)
                    raise Exception("CommandDispatcher did not handle event: " + str(event))

            await asyncio.sleep(0.1)

    def consolidate_replies(self, replies: list):
        is_html = False
        reply_to_send = b""

        # loop through replies list,
        # convert any markdown to html and set is_html
        # for html, set is_html and concat the reply

        for reply in replies:
            # if reply_to_send != b"":
            #     reply_to_send += b"\n"
            if reply['type'] == "html":
                is_html = True
                if isinstance(reply['body'], str):
                    reply_to_send += reply['body'].encode("utf-8")
                else:
                    reply_to_send += reply['body']
            elif reply['type'] == "markdown":
                is_html = True
                if isinstance(reply['body'], str):
                    reply_to_send += Markdown().convert(reply['body']).encode("utf-8")
                else:
                    reply_to_send += Markdown().convert(reply['body'].decode("utf-8")).encode("utf-8")
            else:
                if isinstance(reply['body'], str):
                    reply_to_send += reply['body'].encode("utf-8")
                else:
                    reply_to_send += reply['body']

        return (is_html, reply_to_send)

    async def run_factoid(self, event, stdin_data=b"", recurse_count=0):
        factoid_command_split = event.body.split(" ")
        logger.info("Attempting to run factoid '%s'", factoid_command_split[0])

        # get the factoid from the db/fs
        factoid_content = self.client.factoids.get_content(factoid_command_split[0])
        if factoid_content == None:
            logger.warning("Attempt to run non-existent command '%s'", event.body)
            raise CommandNotFound(f"Command not found for '{factoid_command_split[0]}'")
            
        # first check if a $NUM argument is required but not in the event body
        for x in range(100):
            if "$" + str(x) in factoid_content and len(factoid_command_split) <= x:
                logger.warning("Attempt to run command without correct input '%s'", event.body)
                raise EmptyInput(f"More input is required for '{factoid_command_split[0]}'")

        # then replace all the arguments into the factoid we are going to run
        # we escape quotation marks and wrap the input in quotes
        for x in range(len(factoid_command_split)):
            factoid_content = factoid_content.replace("$" + str(x), '"' + factoid_command_split[x].replace("\"", "\\\"") + '"')
        
        # replace any occurences of $@
        # escape quotation marks, wrap in quotes
        if len(factoid_command_split) > 1:
            factoid_content = factoid_content.replace("$@", '"' + " ".join(factoid_command_split[1:]).replace("\"", "\\\"") + '"')
        elif "$@" in factoid_content:
            logger.warning("Attempt to run command without correct input '%s'", event.body)
            raise EmptyInput(f"Input required for {factoid_command_split[0]}")

        if factoid_content.startswith("<html>") or factoid_content.startswith("[html]"):
            return [{
                "type": "html",
                "body": factoid_content[len("<html>"):]
            }]
        # markdown factoids
        elif factoid_content.startswith("<markdown>") or factoid_content.startswith("[markdown]"):
            return [{
                "type": "markdown",
                "body": factoid_content[len("<markdown>"):]
            }]

        # check if we are being redirected to another command,
        # and if so we run and return the output of that command instead
        if factoid_content.startswith("<cmd>") or factoid_content.startswith("[cmd]"):
            copied_event = copy.deepcopy(event)
            copied_event.body = factoid_content[len("<cmd>"):]
            return await self.parse_and_run_command(copied_event, stdin_data, recurse_count + 1)
        # in case anyone wanted to just write html factoids
        # check if a custom content prefix is being used with a command that is
        # registered with the bot
        else:
            for module, commands in self.client.commands.items():
                for command in commands:
                    if factoid_content.startswith(f"<{command}>") or factoid_content.startswith(f"[{command}]"):
                        copied_event = copy.deepcopy(event)
                        copied_event.body = factoid_content[len(command) + 2:]
                        copied_event.body = command + " " + copied_event.body
                        return await self.parse_and_run_command(copied_event, stdin_data, recurse_count + 1)

        # fallback to just sending the factoid content as text
        return [{
            "type": "text",
            "body": factoid_content
        }]

    async def run_command(self, event, stdin_data=b"", recurse_count=0):
        results = []
        no_commands_found = True
        
        if len(event.body) == 0:
            logger.error("Tried running command but input was empty")
            raise EmptyInput("Input was empty.")

        # first, we check if any of our modules reported this as a command
        for module, commands in self.client.commands.items():
            for command in commands:
                if event.body.startswith(command):
                    # great we found a module with the command
                    # buffer all outputs for further inputs
                    buffering_event = ReplyBufferingEvent(self.client, event, stdin_data, buffer_replies=True)
                    # actually fire the function in the module (buffering happens inside the module)
                    await self.client.send_to_module(module, buffering_event)
                    # append the result to results output
                    results += buffering_event.buffer
                    # do not search factoids
                    no_commands_found = False
        
        # there were no commands found, so we will execute this as a factoid
        if no_commands_found:
            return await self.run_factoid(event, stdin_data, recurse_count)

        return results

    async def parse_and_run_command(self, event, stdin_data=b"", recurse_count=0):
        if recurse_count == 10:
            raise RecursionLimitExceeded("You have exceeded the recursion limit.")

        # first of all, directly execute the commands that eat everything
        for module, commands in self.client.commands.items():
            if isinstance(commands, dict):
                for command, eat_everything in commands.items():
                    if event.body.startswith(command) and eat_everything:
                        buffering_event = ReplyBufferingEvent(self.client, event, stdin_data, buffer_replies=True)
                        await self.client.send_to_module(module, buffering_event)
                        return buffering_event.buffer

        previous_output = stdin_data
        count = 0
        results = []

        # split by | unless escaped
        split_by_redirect = re.split("(?<!\\\\)[|]", event.body)

        for command in split_by_redirect:
            copied_event = copy.deepcopy(event)
            copied_event.body = command.strip().replace("\\|", "|")
            
            # only return results for the last command in the sequence
            if len(split_by_redirect) - 1 == count:
                results = await self.run_command(copied_event, stdin_data=previous_output, recurse_count=recurse_count)
            else:
                output = await self.run_command(copied_event, stdin_data=previous_output, recurse_count=recurse_count)
                is_html, previous_output = self.consolidate_replies(output)

            count = count + 1

        return results

    async def maybe_run_commands(self, event):
        if event.body.startswith(self.client.bot_config.command_prefix):
            # create a fresh copy of the event so we do not mess up other callbacks
            copied_event = copy.deepcopy(event)
            copied_event.body = copied_event.body[len(self.client.bot_config.command_prefix):]

            try:
                # run all commands, outputs a list of concatenated replies which are consolidated
                results = await self.parse_and_run_command(copied_event)
                is_html, reply_to_send = self.consolidate_replies(results)

                reply_to_send = reply_to_send.decode("UTF-8")
                
                # dont send empty strings
                if reply_to_send.strip() == "":
                    return
                
                send_result = None
                if is_html:
                    self.client.queue_html(reply_to_send)
                else:
                    self.client.queue_text(reply_to_send)
            except (CommandNotFound, RecursionLimitExceeded, EmptyInput) as e:
                self.client.queue_text("An error occurred. " + str(e))
        else:
            await self.client.send_to_all_modules(event)
    