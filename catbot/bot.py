import configparser
import asyncio
import os
import sys
import json
import argparse

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)
from nio.log import logger_group

#TODO
from .clients.main_client import MainClient
from .clients.common_client import CommonClient
from .clients.channel_client import ChannelClient

async def run_client(client: CommonClient) -> None:
    await client.login()

    async def after_first_sync():
        print("Awaiting sync")
        await client.synced.wait()
        await client.after_first_sync()

    after_first_sync_task = asyncio.ensure_future(after_first_sync())
    sync_forever_task = asyncio.ensure_future(client.sync_forever(30000, full_state=True))
    
    if isinstance(client, MainClient):
        setup_cached_bots_list = client.setup_cached_bots()
        
        await asyncio.gather(
            # The order here IS significant! You have to register the task to trust
            # devices FIRST since it awaits the first sync
            after_first_sync_task,
            *setup_cached_bots_list,
            sync_forever_task
        )
    else:
        await asyncio.gather(
            # The order here IS significant! You have to register the task to trust
            # devices FIRST since it awaits the first sync
            after_first_sync_task,
            sync_forever_task
        )

async def main(entrypoint_file):
    global_store_path = os.path.realpath("storage/") #TODO accept command line args!

    if not os.path.isdir(global_store_path):
        os.mkdir(global_store_path)

    parser = argparse.ArgumentParser(description='A matrix-nio bot with working E2EE.')
    parser.add_argument('bot_id', metavar='BOT_ID', type=str,
                       help='the bot id (use MAIN to start catbot in main mode)')
    parser.add_argument('--room-id', dest='room_id', metavar='ROOM_ID', type=str,
                       help='the room id to join', required=False)

    args = parser.parse_args()
    main_mode = args.bot_id == "MAIN"
    client = None

    if main_mode:
        client = MainClient(
            global_store_path,
            path_to_run
        )
    else:
        client = ChannelClient(
            global_store_path,
            args.bot_id
        )

    try:
        await run_client(client)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await client.close()
