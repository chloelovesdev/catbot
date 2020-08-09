import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteMemberEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse, RoomMemberEvent,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        self.add_event_callback(self.cb_autojoin_room, InviteMemberEvent)

        self.add_response_callback(self.cb_synced, SyncResponse)

        self.bot_inviter_id = None
        self.bot_just_joined = False
        # self.has_first_sync = False

        print("Channel client woop")

    # async def cb_kicked_left_or_banned(self, room: MatrixRoom, event: RoomMemberEvent):
    #     print("RoomMemberEvent")
    #     print(event)
    #     print(room)
    #     if event.source and event.source['unsigned'] and event.source['unsigned']['replaces_state']:
    #         print("But it replaces state")
    #         return

    async def cb_synced(self, response):
        if self.bot_just_joined and self.bot_config.server.channel in self.rooms:
            print("Bot is now in the room and we have the user data for the room")

            if not self.bot_inviter_id:
                raise Exception("Bot inviter not given, but bot just joined?")#TODO
            
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            #TODO: add matrix event?
            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                print("Inviter has correct power level")
                await self.send_text_to_room("catbot here at your service :)") #TODO: get hello from config file
            else:
                await self.send_text_to_room(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()

            self.bot_just_joined = False
        
        state = "join"
        state_latest_timestamp = 0

        #TODO: copy pasta remova

        # find the latest state event
        # hack around RoomMemberEvent not being given to the channel_client for some reason
        # TODO: fix this mess!

        for room_id, room_info in response.rooms.join.items():
            if room_id == self.bot_config.server.channel:
                for event in room_info.timeline.events:
                    if isinstance(event, RoomMemberEvent) and event.state_key == self.bot_config.server.user_id and event.source['origin_server_ts'] > state_latest_timestamp:
                        state = event.content['membership']
                        state_latest_timestamp = event.source['origin_server_ts']

        for room_id, room_info in response.rooms.leave.items():
            if room_id == self.bot_config.server.channel:
                for event in room_info.timeline.events:
                    if isinstance(event, RoomMemberEvent) and event.state_key == self.bot_config.server.user_id and event.source['origin_server_ts'] > state_latest_timestamp:
                        state = event.content['membership']
                        state_latest_timestamp = event.source['origin_server_ts']
                
        if state == "leave" or state == "ban":
            await self.delete_self()

    async def delete_self(self):
        await self.room_leave(self.bot_config.server.channel)
        print("DELETEBOT")
        sys.stderr.write("DELETEBOT\n")
        sys.stderr.flush()
        sys.exit(1)

    async def cb_autojoin_room(self, room: MatrixRoom, event: InviteMemberEvent):
        print("Autojoin")
        print(room)
        print(event)

        if room.room_id == self.bot_config.server.channel:
            await self.join(room.room_id)
            self.bot_inviter_id = event.sender
            self.bot_just_joined = True

    async def after_first_sync(self):
        # self.has_first_sync = True
        pass
        #await asyncio.sleep(1)
        #await self.send_text_to_room("Hello, channel!")

    #def after_first_sync(self):
    #    self.__only_trust_devices(self.bot_config.owner.session_ids)

    #def __only_trust_devices(self, device_list: Optional[str] = None) -> None:
    #    for olm_device in self.device_store:
    #        if olm_device.device_id in device_list:
    #            self.verify_device(olm_device)
    #        else:
    #            self.blacklist_device(olm_device)