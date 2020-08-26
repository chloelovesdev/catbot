from catbot import module

import aiohttp
import asyncio
import async_timeout

class State(module.Module):
    @module.setup
    async def setup(self, event):
        return [
            "state get",
            "state set",
            "state reset"
        ]

    @module.command("state get", help="Gets state from file")
    async def on_cmd_state_get(self, event):
        state_content = self.bot.factoids.get_content_binary("state-" + event.body.strip())
        if state_content:
            event.reply(state_content)
        else:
            event.reply("uninitialized")

    @module.command("state set", help="Saves state from the first line of input then sends the rest")
    async def on_cmd_state_set(self, event):
        if b"\n" in event.stdin_data:
            stdin_data_split = event.stdin_data.split(b"\n", 1)
            self.bot.factoids.set_content_binary("state-" + event.body.strip(), stdin_data_split[0])
            event.reply(stdin_data_split[1])
        else:
            event.reply("Setting state requires first line as input to state and data to forward.")

    @module.command("state reset", help="Saves state from the first line of input then sends the rest")
    async def on_cmd_state_reset(self, event):
        body = event.body.strip()
        self.bot.factoids.set_content_binary("state-" + body, b"uninitialized")
        event.reply(f"Resetted state for '{body}'")