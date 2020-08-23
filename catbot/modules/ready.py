from catbot import module

class Ready(module.Module):
    @module.setup
    async def setup(self, event):
        event.reply("Bot is now ready")