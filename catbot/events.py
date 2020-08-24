from dataclasses import dataclass

from nio import RoomMessageText

class BotSetupEvent:
    pass

class ReplyBufferingEvent:
    def __init__(self, bot, original_event, stdin_data=b"", state_file=None, buffer_replies=False):
        self.original_event = original_event
        self.bot = bot
        self.buffer_replies = buffer_replies
        self.stdin_data = stdin_data
        self.state_file = None
        self.buffer = []

    def reply(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "text",
                "body": message
            })
            return True

        return self.bot.queue_text(message)

    def reply_html(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "html",
                "body": message
            })
            return True

        return self.bot.queue_html(message)

    def reply_markdown(self, message):
        if self.buffer_replies:
            self.buffer.append({
                "type": "markdown",
                "body": message
            })
            return True

        return self.bot.queue_markdown(message)

    @property
    def body(self):
        if isinstance(self.original_event, RoomMessageText):
            return self.original_event.body

        return None