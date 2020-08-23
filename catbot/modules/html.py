from catbot import module

class HTML(module.Module):
    @module.setup
    async def setup(self, event):
        return ["html"]

    @module.command("html", help="Prints with HTML")
    async def on_cmd_html(self, event):
        event.reply_html(event.stdin_data)