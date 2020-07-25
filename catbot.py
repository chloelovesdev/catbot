import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)

from clients import MainClient

STORE_FOLDER = "storage/"

SESSION_DETAILS_FILE = STORE_FOLDER + "/manual_encrypted_verify.json"

async def run_client(client: CommonClient) -> None:
    await client.login()

    async def after_first_sync():
        print("Awaiting sync")
        await client.synced.wait()

#        client.trust_devices(BOB_ID, BOB_DEVICE_IDS)
#        client.trust_devices(ALICE_USER_ID)

        await client.send_hello_world()

    after_first_sync_task = asyncio.ensure_future(after_first_sync())
    sync_forever_task = asyncio.ensure_future(client.sync_forever(30000, full_state=True))

    await asyncio.gather(
        # The order here IS significant! You have to register the task to trust
        # devices FIRST since it awaits the first sync
        after_first_sync_task,
        sync_forever_task
    )

async def main():
    global_store_path = os.path.realpath("storage/") #TODO accept command line args!

    main_client = MainClient(
        global_store_path
    )

    try:
        await run_client(client)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(
            main()
        )
    except KeyboardInterrupt:
        pass
