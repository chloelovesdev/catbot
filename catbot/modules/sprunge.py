from catbot import module

import aiohttp
import asyncio
import async_timeout

class Sprunge(module.Module):
    @module.setup
    async def setup(self, event):
        return [
            "sprunge"
        ]

    @module.command("sprunge", help="Uploads to sprunge")
    async def on_cmd_sprunge(self, event):
        async with aiohttp.ClientSession() as session:
            with async_timeout.timeout(10):
                data = {"sprunge": event.body}
                async with session.post("http://sprunge.us", data=data) as response:
                    sprunge_url = await response.text()
                    await event.reply(sprunge_url.strip())