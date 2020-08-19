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

        self.add_response_callback(self.cb_channelclient_synced, SyncResponse)
        print("Channel client woop")

    async def cb_channelclient_synced(self, response):
        print(response)
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

        if state == "leave" or state == "ban":
            await self.delete_self()

    async def room_setup(self):
        print("Bot is now in the room and we have the user data for the room")

        if self.bot_inviter_id:
            inviter_room = self.rooms[self.bot_config.server.channel]
            inviter_user = inviter_room.users[self.bot_inviter_id]

            #TODO: add matrix event?
            if self.bot_inviter_id in inviter_room.power_levels.users and inviter_room.power_levels.users[self.bot_inviter_id] >= 50:
                print("Inviter has correct power level")
                await self.send_text_to_room("catbot here at your service :)") #TODO: get hello from config file
            else:
                await self.send_text_to_room(self.bot_inviter_id + " invited me, but does not have the correct power level for me to join (>=50)")
                await self.delete_self()

    async def delete_self(self):
        await self.room_leave(self.bot_config.server.channel)
        print("DELETEBOT")
        sys.stderr.write("DELETEBOT\n")
        sys.stderr.flush()
        sys.exit(1)