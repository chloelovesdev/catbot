import configparser
import asyncio
import os
import sys
import json

from typing import Optional

from nio import (AsyncClient, ClientConfig, DevicesError, Event,InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText,
                 crypto, exceptions, RoomSendResponse)

from .common_client import CommonClient

class MainClient(CommonClient):
    def __init__(self, global_store_path):
        super().__init__(global_store_path=global_store_path, bot_id="MAIN")