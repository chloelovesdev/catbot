import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)

STORE_FOLDER = "nio_store/"

SESSION_DETAILS_FILE = STORE_FOLDER + "/manual_encrypted_verify.json"

class CatBotClient(AsyncClient):
    def __init__(self, homeserver, user='', device_id='', store_path='', config=None, ssl=None, proxy=None, bot_config=None):
        super().__init__(homeserver, user=user, device_id=device_id, store_path=store_path, config=config, ssl=ssl, proxy=proxy)
        self.bot_config = bot_config

        if store_path and not os.path.isdir(store_path):
            os.mkdir(store_path)

        self.add_event_callback(self.cb_autojoin_room, InviteEvent)
        self.add_event_callback(self.cb_print_messages, RoomMessageText)

    async def login(self) -> None:
        # Restore the previous session if we can
        if os.path.exists(SESSION_DETAILS_FILE) and os.path.isfile(SESSION_DETAILS_FILE):
            try:
                with open(SESSION_DETAILS_FILE, "r") as f:
                    config = json.load(f)
                    self.access_token = config['access_token']
                    self.user_id = config['user_id']
                    self.device_id = config['device_id']

                    # This loads our verified/blacklisted devices and our keys
                    self.load_store()
                    print(f"Logged in using stored credentials: {self.user_id} on {self.device_id}")

            except IOError as err:
                print(f"Couldn't load session from file. Logging in. Error: {err}")
            except json.JSONDecodeError:
                print("Couldn't read JSON file; overwriting")

        # We didn't restore a previous session, so we'll log in with a password
        if not self.user_id or not self.access_token or not self.device_id:
            # this calls the login method defined in AsyncClient from nio
            resp = await super().login(self.bot_config.get("catbot", "password"))

            if isinstance(resp, LoginResponse):
                print("Logged in using a password; saving details to disk")
                self.__write_details_to_disk(resp)
            else:
                print(f"Failed to log in: {resp}")
                sys.exit(1)

#    def trust_devices(self, user_id: str, device_list: Optional[str] = None) -> None:
#        print(f"{user_id}'s device store: {self.device_store[user_id]}")

#        for device_id, olm_device in self.device_store[user_id].items():
#            if device_list and device_id not in device_list:
                # a list of trusted devices was provided, but this ID is not in
                # that list. That's an issue.
#                print(f"Not trusting {device_id} as it's not in {user_id}'s pre-approved list.")
#                continue

#            if user_id == self.user_id and device_id == self.device_id:
                # We cannot explictly trust the device @alice is using
#                continue

#            self.verify_device(olm_device)
#            print(f"Trusting {device_id} from user {user_id}")

    def cb_autojoin_room(self, room: MatrixRoom, event: InviteEvent):
        self.join(room.room_id)
        room = self.rooms[ROOM_ID]
        print(f"Room {room.name} is encrypted: {room.encrypted}" )

    async def cb_print_messages(self, room: MatrixRoom, event: RoomMessageText):
        if event.decrypted:
            encrypted_symbol = "🛡 "
        else:
            encrypted_symbol = "⚠️ "
        print(f"{room.display_name} |{encrypted_symbol}| {room.user_name(event.sender)}: {event.body}")
        if "meow" in event.body.lower() and not "chloebot" in event.sender:
            await self.send_hello_world()

    async def send_hello_world(self):
        try:
            await self.room_send(
                room_id=self.bot_config.get("catbot", "dev_channel"),
                message_type="m.room.message",
                content = {
                    "msgtype": "m.text",
                    "body": "meow"
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            print("These are all known devices:")
            device_store: crypto.DeviceStore = device_store
            [print(f"\t{device.user_id}\t {device.device_id}\t {device.trust_state}\t  {device.display_name}") for device in device_store]
            sys.exit(1)

    @staticmethod
    def __write_details_to_disk(resp: LoginResponse) -> None:

        with open(SESSION_DETAILS_FILE, "w") as f:
            json.dump({
                "access_token": resp.access_token,
                "device_id": resp.device_id,
                "user_id": resp.user_id
            }, f)


async def run_client(client: CatBotClient) -> None:
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
    matrix_config = ClientConfig(store_sync_tokens=True)

    bot_config = configparser.ConfigParser()
    root_path = os.path.dirname(os.path.realpath(__file__))
    bot_config_path = os.path.join(root_path, "catbot.cfg")
    bot_config.read(bot_config_path)

    client = CatBotClient(
        bot_config.get("catbot", "base_url"),
        bot_config.get("catbot", "username"),
        store_path=STORE_FOLDER,
        config=matrix_config,
        bot_config=bot_config
#        ssl=False,
#        proxy="http://localhost:8080",
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
