from dataclasses import dataclass

class BotSetupEvent:
    pass

@dataclass
class CommandEvent:
    name: str
    body: str