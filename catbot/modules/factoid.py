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
        
    def __set_factoid_content(self, name, content):
        factoid_path = self.bot.get_factoid_path(name)
        factoid_file = open(factoid_path, "w")
        factoid_file.write(content)
        factoid_file.close()
        return True

    @module.command("factoid get", help="Get the content of a factoid")
    async def on_cmd_factoid_get(self, event):
        if event.body == "":
            await event.reply("Incorrect usage! Use factoid get <name>")
            return

        content = self.bot.get_factoid_content(event.body)

        if content:
            escaped_content = html.escape(content)
            await event.reply_html(f"Factoid content for {event.body}:\n\n<pre>{escaped_content}</pre>")
        else:
            await event.reply(f"Factoid not found.")
        
    @module.command("factoid set", help="Set the content of a factoid")
    async def on_cmd_factoid_set(self, event):
        if not " " in event.body:
            await event.reply("Incorrect usage! Use factoid set <name> <content>")
            return

        body_split = re.split("\n|\r| ", event.body, 1)
        name = body_split[0]
        content = body_split[1]

        if self.__set_factoid_content(name, content):
            await event.reply(f"Factoid {name} set!")
        else:
            await event.reply(f"Failed saving factoid {name}!")