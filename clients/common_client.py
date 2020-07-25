import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)

from python_json_config import ConfigBuilder

def config_validation_steps(builder):
    #TODO
    builder.validate_field_type('server.access_token', str)
    builder.validate_field_type('server.user_id', str)
    builder.validate_field_type('server.device_id', str)

class CommonClient(AsyncClient):
    def __init__(self, global_store_path='', bot_id=""):
        if bot_id == "":
            raise Exception("bot_id required")

        store_path = os.path.join(global_store_path, bot_id)

        if not os.path.isdir(store_path):
            os.mkdir(store_path)

        builder = ConfigBuilder()
        self.bot_config = builder.parse_config(os.path.join(store_path, "config.json"))

        matrix_config = ClientConfig(store_sync_tokens=True)

        super().__init__(self.bot_config.server.url, user=self.bot_config.server.user_id,
                    device_id=self.bot_config.server.device_id, store_path=store_path, config=matrix_config, ssl=True)

        self.add_event_callback(self.cb_autojoin_room, InviteEvent)
        self.add_event_callback(self.cb_print_messages, RoomMessageText)

    async def login(self) -> None:
        self.access_token = self.bot_config.server.access_token
        self.user_id = self.bot_config.server.user_id
        self.device_id = self.bot_config.server.device_id

        print(f"Logged in using stored credentials: {self.user_id} on {self.device_id}")

        # We didn't restore a previous session, so we'll log in with a password
        if not self.user_id or not self.access_token or not self.device_id:
            # this calls the login method defined in AsyncClient from nio
            resp = await super().login(self.bot_config.server.password)

            if isinstance(resp, LoginResponse):
                print("Logged in using a password; saving details to disk")
                self.bot_config.add("server.access_token", resp.access_token)
                self.bot_config.add("server.device_id", resp.access_token)
                self.bot_config.add("server.user_id", resp.access_token)
            else:
                print(f"Failed to log in: {resp}")
                sys.exit(1)
        else:
            self.load_store()

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

    # def cb_autojoin_room(self, room: MatrixRoom, event: InviteEvent):
    #     self.join(room.room_id)
    #     room = self.rooms[ROOM_ID]
    #     print(f"Room {room.name} is encrypted: {room.encrypted}" )

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
                room_id=self.bot_config.server.channel,
                message_type="m.room.message",
                content = {
                    "msgtype": "m.text",
                    "body": "meow"
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            print("These are all known devices:")
            [print(f"\t{device.user_id}\t {device.device_id}\t {device.trust_state}\t  {device.display_name}") for device in self.device_store]
            sys.exit(1)

