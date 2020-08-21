from catbot.modules import module

class Ready(module.Module):
    @module.setup
    async def setup(self, event):
        await event.reply("Bot is now ready")