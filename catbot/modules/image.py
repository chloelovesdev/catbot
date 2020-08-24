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
        print(len(event.stdin_data))
        fp.write(event.stdin_data)
        fp.seek(0)

        print(extension)
        response, maybe_keys = await self.bot.upload(fp, f"image/{extension}", f"image.{extension}")
        fp.close()
        
        if isinstance(response, UploadError):
            print(response)
            event.reply("Error occurred uploading the image. " + str(response))
            return

        self.bot.queue_image(response.content_uri)