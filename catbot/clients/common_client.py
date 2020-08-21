import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from markdown2 import Markdown

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, InviteMemberEvent, SyncResponse,
                 crypto, exceptions, RoomSendResponse, RoomMemberEvent)

from python_json_config import ConfigBuilder

def config_validation_steps(builder):
    #TODO
    builder.validate_field_type('server.access_token', str)
    builder.validate_field_type('server.user_id', str)
    builder.validate_field_type('server.device_id', str)

class CommonClient(AsyncClient):
    def __init__(self, global_store_path='', bot_id="", proxy=None):
        if bot_id == "":
            raise Exception("bot_id required")

        self.global_store_path = global_store_path
        self.bot_id = bot_id

        store_path = os.path.join(global_store_path, bot_id)

        if not os.path.isdir(store_path):
            os.mkdir(store_path)

        # loads in the config unless it doesn't exist
        builder = ConfigBuilder()
        self.config_path = os.path.join(store_path, "config.json")
        if not os.path.exists(self.config_path):
            raise Exception(f"Config {self.config_path} does not exist.")
        self.bot_config = builder.parse_config(self.config_path)

        matrix_config = ClientConfig(store_sync_tokens=True)

        super().__init__(self.bot_config.server.url, user=self.bot_config.server.user_id,
                    device_id=self.bot_config.server.device_id, store_path=store_path, config=matrix_config, ssl=True, proxy=proxy)

        self.bot_inviter_id = None
        self.delay_setup = False
        self.delay_setup_for_keys = False
        self.keys_sent = False
        self.setup_delayed_for = 0 # syncs the setup has been delayed for
        self.has_setup = False

        self.add_event_callback(self.cb_print_messages, RoomMessageText)
        self.add_event_callback(self.cb_room_setup, InviteMemberEvent)

        self.add_response_callback(self.cb_synced, SyncResponse)

    async def login(self) -> None:
        self.access_token = self.bot_config.server.access_token
        self.user_id = self.bot_config.server.user_id
        self.device_id = self.bot_config.server.device_id

        print(self.access_token)
        print(self.user_id)
        print(self.device_id)
        # We didn't restore a previous session, so we'll log in with a password
        if not self.user_id or not self.access_token or not self.device_id:
            # this calls the login method defined in AsyncClient from nio
            resp = await asyncio.wait_for(super().login(self.bot_config.server.password), timeout=60)

            if isinstance(resp, LoginResponse):
                print("Logged in using a password; saving details to disk")
                self.bot_config.add("server.access_token", resp.access_token)
                self.bot_config.add("server.device_id", resp.device_id)
                self.bot_config.add("server.user_id", resp.user_id)
                self.save_config()
            else:
                print(f"Failed to log in: {resp}")
                sys.exit(1)
        else:
            print(f"Logged in using stored credentials: {self.user_id} on {self.device_id}")
            self.load_store()

    async def cb_synced(self, response):
        # find the latest state event
        # hack around RoomMemberEvent not being given to the channel_client for some reason
        # TODO: fix this mess!
        def check_rooms_in_sync(state, state_latest_timestamp, rooms):
            for room_id, room_info in rooms.items():
                if room_id == self.bot_config.server.channel:
                    for event in room_info.timeline.events:
                        if isinstance(event, RoomMemberEvent) and event.state_key == self.bot_config.server.user_id and event.source['origin_server_ts'] > state_latest_timestamp:
                            state = event.content['membership']
                            state_latest_timestamp = event.source['origin_server_ts']
            
            return (state, state_latest_timestamp)

        state = "join"
        state_latest_timestamp = 0
        
        state, state_latest_timestamp = check_rooms_in_sync(state, state_latest_timestamp, response.rooms.join)
        state, state_latest_timestamp = check_rooms_in_sync(state, state_latest_timestamp, response.rooms.leave)
        for room_id, room_info in response.rooms.invite.items():
            if room_id == self.bot_config.server.channel:
                print(room_info)
                for event in room_info.invite_state:
                    if isinstance(event, InviteMemberEvent) and event.state_key == self.bot_config.server.user_id and event.source['origin_server_ts'] > state_latest_timestamp:
                        state = event.content['membership']
                        state_latest_timestamp = event.source['origin_server_ts']

        await self.membership_changed(state)

        # check if the setup is delayed
        # if the room is encrypted, we wait another sync for the keys
        # when all is good, room_setup will be fired

        #print(f"Synced: {response}")
        if self.delay_setup and self.bot_config.server.channel in self.rooms:
            room = self.rooms[self.bot_config.server.channel]
            if room.encrypted:
                print("This room is encrypted and we must wait for another sync which will contain the keys")
                self.delay_setup = False
                self.delay_setup_for_keys = True
                self.setup_delayed_for = 0
                return

            print("cb_synced calling room_setup")
            await self.room_setup()
            self.has_setup = True
            self.delay_setup = False
        elif self.delay_setup:
            self.setup_delayed_for += 1

        if self.delay_setup_for_keys:
            print("Delay setup for keys")
            for olm_device in self.device_store:
                print("Device with key found")
                self.delay_setup_for_keys = False
                await self.room_setup()
                self.has_setup = True
                return
            self.setup_delayed_for += 1

        # if the setup has been delayed for more than 5 syncs,
        # call the room_setup_failed method
        # this is here in case the bot has not been invited/joined or the keys were never sent.
        
        if self.setup_delayed_for > 5:
            await self.room_setup_failed()

    #debug print messages
    #TODO: REMOVE? 
    async def cb_print_messages(self, room: MatrixRoom, event: RoomMessageText):
        # dont print anything thats not from the bot's channel
        if room.room_id != self.bot_config.server.channel:
            # print(room.room_id)
            return

        if event.decrypted:
            encrypted_symbol = "🛡 "
        else:
            encrypted_symbol = "⚠️ "
        print(f"{room.display_name} |{encrypted_symbol}| {room.user_name(event.sender)}: {event.body}")
        if "!devices" in event.body.lower() and not self.bot_config.server.user_id == event.sender:
            print("These are all known devices:")
            [print(f"\t{device.user_id}\t {device.device_id}\t {device.trust_state}\t  {device.display_name}") for device in self.device_store]
        if "meow" in event.body.lower() and not self.bot_config.server.user_id == event.sender:
            await self.send_text("meow")

    async def send_text(self, message):
        # trust the devices from the config every time we send, to prevent olm errors
        self.only_trust_devices(self.bot_config.owner.session_ids)

        try:
            await self.room_send(
                room_id=self.bot_config.server.channel,
                message_type="m.room.message",
                content = {
                    "msgtype": "m.text",
                    "body": message
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            print("olm error")

    async def send_html(self, message):
        # trust the devices from the config every time we send, to prevent olm errors
        self.only_trust_devices(self.bot_config.owner.session_ids)

        try:
            await self.room_send(
                room_id=self.bot_config.server.channel,
                message_type="m.room.message",
                content = {
                    "msgtype": "m.text",
                    "format": "org.matrix.custom.html",
                    "body": message,
                    "formatted_body": message
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            print("olm error")
            
    async def send_markdown(self, message):
        return await self.send_html(Markdown().convert(message))

    async def cb_room_setup(self, room: MatrixRoom, event: InviteMemberEvent):
        print("Room Setup?")
        if event.membership and event.membership == "invite" and room.room_id == self.bot_config.server.channel:
            print("We were invited to our channel!")
            print(room)
            print(event)

            await self.join(room.room_id)
            self.bot_inviter_id = event.sender
            self.delay_setup = True

    def only_trust_devices(self, device_list: Optional[str] = None) -> None:
        for olm_device in self.device_store:
            if device_list == None or olm_device.device_id in device_list:
                self.verify_device(olm_device)
            else:
                self.blacklist_device(olm_device)

    def save_config(self):
        config_as_json = json.dumps(self.bot_config.to_dict())

        # save it to a file
        config_file = open(self.config_path, "w")
        config_file.write(config_as_json)
        config_file.close()

    async def after_first_sync(self):
        if not self.bot_config.server.channel in self.rooms:
            self.delay_setup = True
        else:
            print("after_first_sync calling room_setup")
            await self.room_setup()
            self.has_setup = True

    async def room_setup(self):
        raise Exception("Room setup not implemented")

    async def room_setup_failed(self):
        print("Setup failed!")
        print("Setup failed!")
        print("Setup failed!")
        print("Setup failed!")
        raise Exception("Setup failed (maybe bot is not in/invited to room?)")

    async def membership_changed(self, state):
        pass