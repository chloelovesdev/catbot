import configparser
import asyncio
import os
import sys
import json
import logging

from typing import Optional

from markdown2 import Markdown

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, InviteMemberEvent, SyncResponse,
                 crypto, exceptions, RoomSendResponse, RoomMemberEvent)

from nio.crypto.device import TrustState
from nio.store.database import SqliteStore

from python_json_config import ConfigBuilder

logger = logging.getLogger(__name__)

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

        matrix_config = ClientConfig(store_sync_tokens=True, store=SqliteStore)

        super().__init__(self.bot_config.server.url, user=self.bot_config.server.user_id,
                    device_id=self.bot_config.server.device_id, store_path=store_path, config=matrix_config, ssl=True, proxy=proxy)

        self.bot_inviter_id = None
        self.delay_setup = False
        self.delay_setup_for_keys = False
        self.keys_sent = False
        self.setup_delayed_for = 0 # syncs the setup has been delayed for
        self.has_setup = False

        self.add_event_callback(self.cb_room_setup, InviteMemberEvent)

        self.add_response_callback(self.cb_synced, SyncResponse)

    async def login(self) -> None:
        self.access_token = self.bot_config.server.access_token
        self.user_id = self.bot_config.server.user_id
        self.device_id = self.bot_config.server.device_id

        if self.user_id == self.bot_config.server.stored_for_user_id:
            logger.info("Using user ID %s and device ID %s", self.user_id, self.device_id)

        # We didn't restore a previous session, so we'll log in with a password
        if not self.user_id or not self.access_token or not self.device_id or self.user_id != self.bot_config.server.stored_for_user_id:
            # this calls the login method defined in AsyncClient from nio
            logger.info("Bot is performing a login with user %s", self.bot_config.server.user_id)
            resp = await asyncio.wait_for(super().login(self.bot_config.server.password), timeout=60)

            if isinstance(resp, LoginResponse):
                logger.info("Logged in using a password; saving details to disk")
                self.bot_config.add("server.access_token", resp.access_token)
                self.bot_config.add("server.device_id", resp.device_id)
                self.bot_config.add("server.user_id", resp.user_id)
                self.bot_config.add("server.stored_for_user_id", resp.user_id)
                self.save_config()
            else:
                logger.info(f"Failed to log in: %s", resp)
                sys.exit(1)
        else:
            logger.info("Logged in using stored credentials: user %s on device %s", self.user_id, self.device_id)
            self.load_store()

    async def cb_synced(self, response):
        logger.info("Bot synced with server")
        
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
                for event in room_info.invite_state:
                    if isinstance(event, InviteMemberEvent) and event.state_key == self.bot_config.server.user_id and event.source['origin_server_ts'] > state_latest_timestamp:
                        state = event.content['membership']
                        state_latest_timestamp = event.source['origin_server_ts']

        await self.membership_changed(state)

        # check if the setup is delayed
        # if the room is encrypted, we wait another sync for the keys
        # when all is good, room_setup will be fired

        if self.delay_setup and self.bot_config.server.channel in self.rooms:
            room = self.rooms[self.bot_config.server.channel]
            if room.encrypted:
                logger.warning("This room is encrypted and we must wait for another sync which will contain the keys")
                self.delay_setup = False
                self.delay_setup_for_keys = True
                self.setup_delayed_for = 0
                return

            logger.debug("cb_synced calling room_setup")
            self.only_trust_from_config()
            await self.room_setup()
            self.has_setup = True
            self.delay_setup = False
        elif self.delay_setup:
            self.setup_delayed_for += 1
            logger.warning("Setup delayed (maybe you need to invite the bot to the room?)")

        if self.delay_setup_for_keys:
            logger.info("Delaying the bot's setup until we have the keys")

            for olm_device in self.device_store:
                logger.info("We have found a key in the device store. Bot will now setup.")

                self.delay_setup_for_keys = False
                self.only_trust_from_config()
                await self.room_setup()
                self.has_setup = True
                return
            self.setup_delayed_for += 1

        # if the setup has been delayed for more than 5 syncs,
        # call the room_setup_failed method
        # this is here in case the bot has not been invited/joined or the keys were never sent.
        
        if self.setup_delayed_for > 5:
            await self.room_setup_failed()

    async def send_text(self, message):
        # trust the devices from the config every time we send, to prevent olm errors
        self.only_trust_from_config()

        try:
            return await self.room_send(
                room_id=self.bot_config.server.channel,
                message_type="m.room.message",
                content = {
                    "msgtype": "m.text",
                    "body": message
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            logger.error("Bot threw an olm error when trying to send text (did you forget to trust the devices?)")
            return None

    async def send_html(self, message):
        # trust the devices from the config every time we send, to prevent olm errors
        self.only_trust_from_config()

        try:
            return await self.room_send(
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
            logger.error("Bot threw an olm error when trying to send HTML (did you forget to trust the devices?)")
            return None

    async def send_image(self, url, body="image"):
        # trust the devices from the config every time we send, to prevent olm errors
        self.only_trust_from_config()

        try:
            return await self.room_send(
                room_id=self.bot_config.server.channel,
                message_type="m.room.message",
                content = {
                    "msgtype": "m.image",
                    "url": url,
                    "body": body
                }
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            logger.error("Bot threw an olm error when trying to send an image (did you forget to trust the devices?)")
            return None

    async def send_markdown(self, message):
        return await self.send_html(Markdown().convert(message))

    async def cb_room_setup(self, room: MatrixRoom, event: InviteMemberEvent):
        logger.info("Bot was invited to a room.")
        
        if event.membership and event.membership == "invite" and room.room_id == self.bot_config.server.channel:
            logger.info("Channel we were invited to is the one the bot is configured for. Attempting to join.")
            await self.join(room.room_id)
            self.bot_inviter_id = event.sender
            self.delay_setup = True
    
    def only_trust_from_config(self):
        self.__only_trust(self.bot_config.trust.to_dict() if self.bot_config.trust else None)

    def __only_trust(self, user_devices_dict) -> None:
        if self.bot_config.server.channel in self.rooms:
            if not self.rooms[self.bot_config.server.channel].encrypted:
                return

        for olm_device in self.device_store:
            if user_devices_dict == None:
                if olm_device.trust_state != TrustState.verified:
                    logger.info("Verifying device %s", olm_device.device_id)
                    self.unblacklist_device(olm_device)
                    self.verify_device(olm_device)
            elif olm_device.user_id in user_devices_dict and user_devices_dict[olm_device.user_id] == None:
                if olm_device.trust_state != TrustState.verified:
                    logger.info("Verifying device %s", olm_device.device_id)
                    self.unblacklist_device(olm_device)
                    self.verify_device(olm_device)
            elif olm_device.user_id in user_devices_dict and olm_device.device_id in user_devices_dict[olm_device.user_id]:
                if olm_device.trust_state != TrustState.verified:
                    logger.info("Verifying device %s", olm_device.device_id)
                    self.unblacklist_device(olm_device)
                    self.verify_device(olm_device)
            else:
                if olm_device.trust_state != TrustState.blacklisted:
                    logger.info("Blacklisting device %s", olm_device.device_id)
                    self.unverify_device(olm_device)
                    self.blacklist_device(olm_device)

    def save_config(self):
        config_as_json = json.dumps(self.bot_config.to_dict(), indent=4)

        # save it to a file
        config_file = open(self.config_path, "w")
        config_file.write(config_as_json)
        config_file.close()

    async def after_first_sync(self):
        if not self.bot_config.server.channel in self.rooms:
            logger.warning("Bot is not in the room. Delaying setup.")
            self.delay_setup = True
        else:
            logger.info("Setting up the room after the first sync")
            await self.room_setup()
            self.has_setup = True

    async def room_setup(self):
        raise Exception("Room setup not implemented")

    async def room_setup_failed(self):
        logger.error("Setup failed!")
        logger.error("Setup failed!")
        logger.error("Setup failed!")
        logger.error("Setup failed!")

        raise Exception("Setup failed (maybe bot is not in/invited to room?)")

    async def membership_changed(self, state):
        pass