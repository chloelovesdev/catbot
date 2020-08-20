from catbot.events import BotSetupEvent, CommandEvent

def setup(func):
    def ret_fun(*args, **kwargs):
        print(args)
        if isinstance(args[1], BotSetupEvent):
            return func(*args, **kwargs)
        else:
            return None
    return ret_fun

def command(*args, **kwargs):
    print(args)
    print(kwargs)
    def ret_fun(*inner_args, **inner_kwargs):
        print("called")
        print(inner_args)
        print(inner_kwargs)
        if len(args) > 1 and isinstance(args[1], CommandEvent):
            return func(*inner_args, **inner_kwargs)
        else:
            return None
    print("return")
    return ret_fun

class command(object):
    def __init__(self, name, help=""):
        self.name = name
        self.help = help

    def __call__(self, func):
        decorator_self = self
        async def wrappee(*args, **kwargs):
            if len(args) > 1 and isinstance(args[1], CommandEvent):
                if args[1].name == self.name:
                    return await func(*args, **kwargs)
            return None
        return wrappee

class Module:
    def __init__(self, client):
        self.client = client