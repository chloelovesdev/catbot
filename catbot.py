import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)

STORE_FOLDER = "storage/"

SESSION_DETAILS_FILE = STORE_FOLDER + "/manual_encrypted_verify.json"

async def client_task(client: CatBotClient) -> None:
    await client.login()

    async def after_first_sync():
        print("Awaiting sync")
        await client.synced.wait()

#        client.trust_devices(BOB_ID, BOB_DEVICE_IDS)
#        client.trust_devices(ALICE_USER_ID)

        await client.send_hello_world()

    after_first_sync_task = asyncio.ensure_future(after_first_sync())
    sync_forever_task = asyncio.ensure_future(client.sync_forever(30000, full_state=True))

    return asyncio.gather(
        # The order here IS significant! You have to register the task to trust
        # devices FIRST since it awaits the first sync
        after_first_sync_task,
        sync_forever_task
    )

async def main():
    matrix_config = ClientConfig(store_sync_tokens=True)
    main_client = MainClient(
        bot_config.get("catbot", "base_url"),
        bot_config.get("catbot", "username"),
        store_path=STORE_FOLDER,
        config=matrix_config,
    )

    try:
        #await run_client(client)
        client_task = asyncio.create_task(
            client_task(main_client)
        )
        await client_methods_tasked
    except (asyncio.CancelledError, KeyboardInterrupt):
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(
            main()
        )
    except KeyboardInterrupt:
        pass
