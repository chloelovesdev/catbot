from catbot.modules import module

class Ping(module.Module):
    @module.setup
    async def setup(self, event):
        return ["ping"]

    @module.command("ping", help="Replies with pong")
    async def on_cmd_ping(self, event):
        await self.bot.send_text_to_room("Pong!")

print("Test")