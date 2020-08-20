from catbot.modules import module

class Ready(module.Module):
    @module.setup
    async def setup(self, event):
        await self.bot.send_text("Bot is now ready")

print("Test")