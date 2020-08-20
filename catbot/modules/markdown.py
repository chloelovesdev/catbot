from catbot.modules import module

class Markdown(module.Module):
    @module.setup
    async def setup(self, event):
        return ["ping"]

    @module.command("markdown", help="Prints with markdown")
    async def on_cmd_ping(self, event):
        await self.bot.send_markdown(event.body)

print("Test")