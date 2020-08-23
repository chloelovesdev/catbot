from catbot import module

from nio import UploadError

import os
import tempfile
import base64
import time

class Image(module.Module):
    @module.setup
    async def setup(self, event):
        return ["image"]

    @module.command("image", help="Upload and send an image (base64)")
    async def on_cmd_image(self, event):
        extension = event.body.strip()
        
        fp = tempfile.TemporaryFile()
        fp.write(event.stdin_data)
        fp.seek(0)

        response, maybe_keys = await self.bot.upload(fp, f"image/{extension}", f"image.{{extension}}")
        if isinstance(response, UploadError):
            await event.reply("Error occurred uploading the image.")
            return
            
        fp.close()
        self.bot.queue_image(response.content_uri)