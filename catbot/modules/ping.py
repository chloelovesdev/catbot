from catbot import module

class Ping(module.Module):
    @module.setup
    async def setup(self, event):
        return ["ping"]

    @module.command("ping", help="Replies with pong")
    async def on_cmd_ping(self, event):
        event.reply("Pong!")