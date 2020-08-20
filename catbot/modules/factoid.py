from catbot.modules import module

class Factoid(module.Module):
    @module.setup
    async def setup(self, event):
        return [
            "factoid get",
            "factoid set"
        ]

    @module.command("factoid get", help="Get the content of a factoid")
    async def on_cmd_factoid_get(self, event):
        await self.bot.send_text_to_room("Pong!")
        
    @module.command("factoid set", help="Get the content of a factoid")
    async def on_cmd_factoid_get(self, event):
        await self.bot.send_text_to_room("Pong!")

print("Test")