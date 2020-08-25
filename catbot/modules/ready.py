from catbot import module

from catbot.clients import TestingChannelClient

class Ready(module.Module):
    @module.setup
    async def setup(self, event):
        if not isinstance(self.bot, TestingChannelClient):
            event.reply("Bot is now ready")