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
        
        print("image started")
        start_time = time.time()
        fp = tempfile.TemporaryFile()
        fp.write(event.stdin_data)
        fp.seek(0)
        end_time = time.time()
        duration = end_time - start_time
        print(f"image write took {duration}s")

        start_time = time.time()
        response, maybe_keys = await self.bot.upload(fp, f"image/{extension}", f"image.{{extension}}")
        if isinstance(response, UploadError):
            await event.reply("Error occurred uploading the image.")
            return
        end_time = time.time()
        duration = end_time - start_time
        print(f"upload took {duration}s")
            
        fp.close()

        start_time = time.time()
        self.bot.queue_image(response.content_uri)
        end_time = time.time()
        duration = end_time - start_time
        print(f"send_image took {duration}s")