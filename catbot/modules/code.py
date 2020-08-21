from catbot import module

import html

class Code(module.Module):
    @module.setup
    async def setup(self, event):
        return ["code"]

    @module.command("code", help="Prints in <pre> container")
    async def on_cmd_ping(self, event):
        escaped_body = html.escape(event.body)
        await event.reply_html(f"<pre>{escaped_body}</pre>")