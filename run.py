#!/usr/bin/python3

import asyncio
import logging

from catbot.bot import main

if __name__ == "__main__":
    FORMAT = '[%(asctime)-15s] [%(name)s] %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, datefmt="%d/%m/%Y %H:%M:%S")

    try:
        asyncio.run(
            main(__file__)
        )
    except KeyboardInterrupt:
        pass
