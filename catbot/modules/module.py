from catbot.events import BotSetupEvent, ReplyBufferingEvent

from nio import (RoomMessageText)

def setup(func):
    def ret_fun(*args, **kwargs):
        print(args)
        if len(args) > 1 and isinstance(args[1], ReplyBufferingEvent) and isinstance(args[1].original_event, BotSetupEvent):
            return func(*args, **kwargs)
        else:
            return None
    return ret_fun

def message(func):
    def ret_fun(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], ReplyBufferingEvent) and isinstance(args[1].original_event, RoomMessageText):
            return func(*args, **kwargs)
        else:
            return None
    return ret_fun

class command(object):
    def __init__(self, name, help=""):
        self.name = name
        self.help = help

    def __call__(self, func):
        decorator_self = self
        
        async def wrappee(*args, **kwargs):
            if len(args) > 1 and isinstance(args[1], ReplyBufferingEvent) and isinstance(args[1].original_event, RoomMessageText):
                if args[1].original_event.body.startswith(self.name):
                    # remove the command name from the body
                    # and also strip away any spaces before the command
                    args[1].original_event.body = args[1].original_event.body[len(self.name):].lstrip()
                    return await func(*args, **kwargs)
            return None
        return wrappee

class Module:
    def __init__(self, bot):
        self.bot = bot