from catbot.modules import module

class Markdown(module.Module):
    @module.setup
    async def setup(self, event):
        return ["markdown"]

    @module.command("markdown", help="Prints with markdown")
    async def on_cmd_ping(self, event):
        await event.reply_markdown(event.body)