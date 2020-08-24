from catbot import module

import os
import re
import html

class Factoid(module.Module):
    @module.setup
    async def setup(self, event):
        return {
            "factoid get": True,
            "factoid set": True
        }

    @module.command("factoid get", help="Get the content of a factoid")
    async def on_cmd_factoid_get(self, event):
        if event.body == "":
            event.reply("Incorrect usage! Use factoid get <name>")
            return

        content = self.bot.get_factoid_content(event.body)

        if content:
            escaped_content = html.escape(content)
            event.reply_html(f"Factoid content for {event.body}:\n\n<pre>{escaped_content}</pre>")
        else:
            event.reply(f"Factoid not found.")
        
    @module.command("factoid set", help="Set the content of a factoid")
    async def on_cmd_factoid_set(self, event):
        if not " " in event.body:
            event.reply("Incorrect usage! Use factoid set <name> <content>")
            return

        body_split = re.split("\n|\r| ", event.body, 1)
        name = body_split[0]
        content = body_split[1]

        if self.bot.set_factoid_content(name, content):
            event.reply(f"Factoid {name} set!")
        else:
            event.reply(f"Failed saving factoid {name}!")