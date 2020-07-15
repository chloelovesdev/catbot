import configparser
import os
import asyncio

from nio import AsyncClient, MatrixRoom, RoomMessageText

config = configparser.ConfigParser()
root_path = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(root_path, "catbot.cfg")
config.read(config_path)

async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
    if "meow" in event.body.lower():
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content = {
                "msgtype": "m.text",
                "body": "meow"
            }
        )
    print(
        f"Message received in room {room.display_name}\n"
        f"{room.user_name(event.sender)} | {event.body}"
    )

async def main() -> None:

    base_url = config.get("catbot", "base_url")
    username = config.get("catbot", "username")

    client = AsyncClient(base_url, username)
    client.add_event_callback(message_callback, RoomMessageText)

    password = config.get("catbot", "password")
    device_name = config.get("catbot", "device_name")

    print(await client.login(password=password, device_name=device_name))
    # "Logged in as @alice:example.org device id: RANDOMDID"
    
    # If you made a new room and haven't joined as that user, you can use
    # await client.join("your-room-id")

    dev_channel = config.get("catbot", "dev_channel")

    await client.room_send(
        # Watch out! If you join an old room you'll see lots of old messages
        room_id=dev_channel,
        message_type="m.room.message",
        content = {
            "msgtype": "m.text",
            "body": "Hello world!"
        }
    )
    await client.sync_forever(timeout=30000) # milliseconds

asyncio.get_event_loop().run_until_complete(main())
