from catbot import module

class Markdown(module.Module):
    @module.setup
    async def setup(self, event):
        return ["markdown"]

    @module.command("markdown", help="Prints with markdown")
    async def on_cmd_markdown(self, event):
        event.reply_markdown(event.stdin_data)