from catbot.modules import module

class Strip(module.Module):
    @module.setup
    async def setup(self, event):
        return [
            "strip"
        ]

    @module.command("strip", help="Strips new lines and spaces from the start/end of the input")
    async def on_cmd_strip(self, event):
        await event.reply(event.body.strip())