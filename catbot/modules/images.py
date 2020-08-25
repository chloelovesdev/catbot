from catbot import module

from nio import UploadError

import os
import tempfile
import base64
import time
import aiohttp

class Images(module.Module):
    @module.setup
    async def setup(self, event):
        return ["curlimages"]

    @module.command("curlimages", help="Upload and send images from urls")
    async def on_cmd_curlimages(self, event):
        print("in curlimages")
        image_urls = event.stdin_data.split(b"\n")

        async with aiohttp.ClientSession() as session:
            print("Session created")
            for image_url in image_urls:
                print("image " + str(image_url))
                try:
                    image_url = image_url.decode("utf-8")
                except:
                    event.reply("Could not decode image URL: " + str(image_url))
                    continue
                
                image_url = image_url.strip()
                if image_url == "":
                    continue

                extension = "".join(image_url.split(".")[-1:])
                mime_type = f"image/{extension}"
                if extension == "jpg":
                    mime_type = "image/jpeg"

                print("get " + image_url)
                async with session.get(image_url) as image_resp:
                    image_data = await image_resp.read()

                    fp = tempfile.TemporaryFile()
                    fp.write(image_data)
                    fp.seek(0)
                    print("AA")
                    response, maybe_keys = await self.bot.upload(fp, mime_type, f"image.{extension}")
                    print("AAA")
                    fp.close()

                    if isinstance(response, UploadError):
                        event.reply("Error occurred uploading the image. " + str(response))
                        continue

                    self.bot.queue_image(response.content_uri)