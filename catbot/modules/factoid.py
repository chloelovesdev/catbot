from catbot.modules import module
import os
import re

class Factoid(module.Module):
    @module.setup
    async def setup(self, event):
        self.factoid_dir_path = os.path.realpath(os.path.join(self.bot.global_store_path, "factoids"))
        if not os.path.isdir(self.factoid_dir_path):
            os.mkdir(self.factoid_dir_path)

        return [
            "factoid get",
            "factoid set"
        ]

    def __get_factoid_path(self, name):
        name = name.replace("/", "").replace(".", "").replace("\\", "")
        return os.path.join(self.factoid_dir_path, name)

    def __get_factoid_content(self, name):
        factoid_path = self.__get_factoid_path(name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path, "r")
            content = factoid_file.read()
            factoid_file.close()
            return content
        else:
            return None
        
    def __set_factoid_content(self, name, content):
        factoid_path = self.__get_factoid_path(name)
        factoid_file = open(factoid_path, "w")
        factoid_file.write(content)
        factoid_file.close()
        return True

    @module.command("factoid get", help="Get the content of a factoid")
    async def on_cmd_factoid_get(self, event):
        if event.body == "":
            await self.bot.send_text("Incorrect usage! Use factoid get <name>")
            return

        print("Get ran")
        content = self.__get_factoid_content(event.body)

        if content:
            await self.bot.send_html(f"Factoid content for {event.body}:\n\n<pre>{content}</pre>")
        else:
            await self.bot.send_text(f"Factoid not found.")
        
    @module.command("factoid set", help="Set the content of a factoid")
    async def on_cmd_factoid_set(self, event):
        if not " " in event.body:
            await self.bot.send_text("Incorrect usage! Use factoid set <name> <content>")
            return

        body_split = re.split("\n|\r| ", event.body, 1)
        name = body_split[0]
        content = body_split[1]

        if self.__set_factoid_content(name, content):
            await self.bot.send_text(f"Factoid {name} set!")
        else:
            await self.bot.send_text(f"Failed saving factoid {name}!")

    @module.message
    async def on_factoid(self, event):
        if event.body.startswith(self.bot.bot_config.factoid_prefix):
            pass

print("Test")