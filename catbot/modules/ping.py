from catbot.modules import module

class Ping(module.Module):
    @module.command("ping", help="Hello there")
    async def on_cmd_ping(self, event):
        await self.client.send_text_to_room("pong")

print("Test")