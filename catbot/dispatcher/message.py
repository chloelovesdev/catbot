import asyncio

from nio import RoomSendError

class MessageDispatcher:
    def __init__(self, client):
        self.client = client
        self.queue = []

    async def start(self):
        while True:
            if len(self.queue) > 0:
                message = self.queue.pop(0)
                if message['type'] == "text":
                    result = await self.client.send_text(message['body'])
                elif message['type'] == "html":
                    result = await self.client.send_html(message['body'])
                elif message['type'] == "markdown":
                    result = await self.client.send_markdown(message['body'])
                elif message['type'] == "image":
                    result = await self.client.send_image(message['url'], message['body'] if "body" in message else "image")
                else:
                    raise Exception("Unknown message type to dispatch")

                # usually an olm error
                if result == None:
                    await self.client.send_text("Send failed (keys not setup?)")
                # couldn't send message to the room for some reason
                elif isinstance(result, RoomSendError):
                    await self.client.send_text(str(result))

            await asyncio.sleep(0.1)