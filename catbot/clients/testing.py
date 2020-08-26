
from catbot.clients import ChannelClient

from python_json_config.config_node import ConfigNode

from nio import (RoomMessageText, UploadResponse)

import time
import os
import json
import base64
import io
import logging

from aiofiles.threadpool.binary import AsyncBufferedReader
from aiofiles.threadpool.text import AsyncTextIOWrapper

SynchronousFile = (
    io.TextIOBase,
    io.BufferedReader,
    io.BufferedRandom,
    io.FileIO
)
AsyncFile = (AsyncBufferedReader, AsyncTextIOWrapper)

logger = logging.getLogger(__name__)

class TestingChannelClient(ChannelClient):
    def __create_testing_client_config(self, config_path):
        # give our config data
        logger.debug("Writing testing bot configuration")

        bot_config = ConfigNode({})
        bot_config.add("server.url", "https://loves.shitposting.chat")
        bot_config.add("server.user_id", "@bot:loves.shitposting.chat")
        bot_config.add("server.device_name", "TESTING")
        bot_config.add("server.channel", "#testing:loves.shitposting.chat")
        bot_config.add("server.password", "testingpassword")

        bot_config.add("owner.user_id", "@bot:loves.shitposting.chat")
        bot_config.add("owner.session_ids", ["TJXGVHDQYT"])

        # dump the config's dictionary
        config_as_json = json.dumps(bot_config.to_dict())

        # save it to a file
        config_file = open(config_path, "w")
        config_file.write(config_as_json)
        config_file.close()

    def __init__(self, global_store_path):
        store_path = os.path.join(global_store_path, "TESTING")
        if not os.path.isdir(store_path):
            os.mkdir(store_path)

        config_path = os.path.join(store_path, "config.json")
        self.__create_testing_client_config(config_path)

        super().__init__(global_store_path=global_store_path, bot_id="TESTING")

        self.output = []

    async def upload(self,
        data_provider,
        content_type="application/octet-stream",
        filename=None,
        encrypt=False,
        monitor=None,
        filesize=None):
        if isinstance(data_provider, SynchronousFile):
            data = data_provider.read()
        elif isinstance(data_provider, AsyncFile):
            data = await data_provider.read()

        return UploadResponse.from_dict({"content_uri": "data:" + content_type + ";base64," + base64.b64encode(data).decode("UTF-8")}), None

    async def run_testing_command(self, command):
        if not self.has_setup:
            await self.room_setup()

        event = RoomMessageText.from_dict({
                'room_id': '#testing:bot',
                'type': 'm.room.message',
                'content': {
                    'msgtype': 'm.text',
                    'body': command
                },
                'event_id': 'testingevent',
                'sender': '@tester:bot',
                'origin_server_ts': int(time.time())
            })

        logger.info("Running testing command with TestingChannelClient: '%s'", command)
        await self.command_dispatcher.maybe_run_commands(event)

        logger.info("Test command finished, returning output")
        return self.message_dispatcher.queue