import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event, InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, SyncResponse,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

class ChannelClient(CommonClient):
    def __init__(self, global_store_path, bot_id):
        super().__init__(global_store_path=global_store_path, bot_id=bot_id)

        self.add_event_callback(self.cb_autojoin_room, InviteEvent)
        print("Channel client woop")

    def cb_autojoin_room(self, room: MatrixRoom, event: InviteEvent):
        print(room)
        print(event)
    
    #def after_first_sync(self):
    #    self.__only_trust_devices(self.bot_config.owner.session_ids)

    #def __only_trust_devices(self, device_list: Optional[str] = None) -> None:
    #    for olm_device in self.device_store:
    #        if olm_device.device_id in device_list:
    #            self.verify_device(olm_device)
    #        else:
    #            self.blacklist_device(olm_device)