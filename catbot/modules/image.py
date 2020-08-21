from catbot.modules import module

from nio import UploadError

import os
import tempfile
import base64

class Image(module.Module):
    @module.setup
    async def setup(self, event):
        return ["image"]

    @module.command("image", help="Upload and send an image (base64)")
    async def on_cmd_image(self, event):
        if not " " in event.body:
            await event.reply("Incorrect usage: image <type> <base64 data>")
            return

        body_split = event.body.strip().split(" ", 1)
        
        fp = tempfile.TemporaryFile()
        fp.write(base64.b64decode(body_split[1]))
        fp.seek(0)
        response, maybe_keys = await self.bot.upload(fp, f"image/{body_split[0]}", f"image.{body_split[0]}")
        if isinstance(response, UploadError):
            await event.reply("Error occurred uploading the image.")
            return

        await self.bot.send_image(response.content_uri)
        fp.close()