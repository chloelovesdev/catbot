from dataclasses import dataclass

from nio import RoomMessageText

class BotSetupEvent:
    pass

class ReplyBufferingEvent:
    def __init__(self, bot, original_event, buffer_replies=False):
        self.original_event = original_event
        self.bot = bot
        self.buffer_replies = buffer_replies
        self.buffer = []

    async def reply(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "text",
                "body": message
            })
            return True

        return await self.bot.send_text(message)

    async def reply_html(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "html",
                "body": message
            })
            return True

        return await self.bot.send_html(message)

    async def reply_markdown(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "markdown",
                "body": message
            })
            return True

        return await self.bot.send_markdown(message)

    @property
    def body(self):
        if isinstance(self.original_event, RoomMessageText):
            return self.original_event.body

        return None