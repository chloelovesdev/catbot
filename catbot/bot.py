import asyncio
import os
import sys
import json
import argparse
import logging

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)
from nio.log import logger_group

from catbot.clients import (MainClient, CommonClient, ChannelClient)
from catbot.management import ManagementServer

from catbot.log import setup_logger

logger = logging.getLogger(__name__)

async def run_client(client: CommonClient) -> None:
    await client.login()

    async def after_first_sync():
        logger.info("Awaiting the first sync from the Matrix server")
        await client.synced.wait()
        
        logger.info("Executing after_first_sync() on client")
        await client.after_first_sync()

    after_first_sync_task = asyncio.ensure_future(after_first_sync())
    sync_forever_task = asyncio.ensure_future(client.sync_forever(30000, full_state=True))
    
    if isinstance(client, MainClient):
        setup_cached_bots_list = client.setup_cached_bots()
        management_server = ManagementServer(client)
        client.management_server = management_server
        
        await asyncio.gather(
            # The order here IS significant! You have to register the task to trust
            # devices FIRST since it awaits the first sync
            management_server.start(),
            after_first_sync_task,
            *setup_cached_bots_list,
            sync_forever_task
        )
    else:
        await asyncio.gather(
            # The order here IS significant! You have to register the task to trust
            # devices FIRST since it awaits the first sync
            after_first_sync_task,
            *client.dispatcher_tasks(),
            sync_forever_task
        )

async def main(entrypoint_file):
    global_store_path = os.path.realpath("storage/") #TODO accept command line args!

    if not os.path.isdir(global_store_path):
        os.mkdir(global_store_path)

    parser = argparse.ArgumentParser(description='A matrix-nio bot with working E2EE.')
    parser.add_argument('bot_id', metavar='BOT_ID', type=str,
                       help='the bot id (use MAIN to start catbot in main mode)')
    parser.add_argument('--management-url', dest='management_url', action='store', # TODO: seperate argparse instances for channel and main
                        help='The URL exposed for the management server (not used for main bot) (example: http://localhost:8080)')

    setup_logger()
    
    args = parser.parse_args()
    logger.info("Arguments parsed successfully")

    main_mode = args.bot_id == "MAIN"
    client = None

    if main_mode:
        logger.info("Creating main client with ID %s", args.bot_id)

        client = MainClient(
            global_store_path,
            entrypoint_file
        )
    else:
        logger.info("Creating channel client with ID %s", args.bot_id)

        client = ChannelClient(
            global_store_path,
            args.bot_id,
            args.management_url
        )

    try:
        await run_client(client)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await client.close()
