#!/usr/bin/python3

import asyncio

from catbot.bot import main

if __name__ == "__main__":
    try:
        asyncio.run(
            main(__file__)
        )
    except KeyboardInterrupt:
        pass
