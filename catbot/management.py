import aiohttp
from aiohttp import web
import aiohttp_jinja2, jinja2

import os
import json
import logging

from catbot.clients import TestingChannelClient
from catbot.managers import FileBasedFactoidManager

logger = logging.getLogger(__name__)

def peer_data(request):
    data = request.transport.get_extra_info('peername')
    if len(data) > 0:
        return data[0]
    else:
        return "UNKNOWN"

class ManagementServer:
    def __init__(self, client):
        logger.info("Initializing management server")

        static_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "static")
        static_path = os.path.realpath(static_path)
        logger.info("Static folder: %s", static_path)

        self.client = client

        self.app = web.Application()
        self.app.router.add_routes([
            web.get('/', self.index),
            web.get('/factoid/{name}', self.factoid),
            web.post('/factoid/{name}/save', self.factoid_save),
            web.post('/test', self.factoid_test),
            web.static('/static', static_path)
        ])

        templates_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "templates")
        templates_path = os.path.realpath(templates_path)
        logger.info("Templates folder: %s", templates_path)

        self.factoids = FileBasedFactoidManager(client.global_store_path)

        aiohttp_jinja2.setup(self.app,
            loader=jinja2.FileSystemLoader(templates_path))

    async def start(self):
        logger.info("Attempting to start management server")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 8080)
        await site.start()
        
    async def stop(self):
        logger.info("Stopping management server")
        await self.runner.cleanup()

    @aiohttp_jinja2.template('factoids/index.html')
    async def index(self, request):
        logger.info("User %s requesting index", peer_data(request))
        factoids = self.factoids.list_of()
        factoid_content = self.factoids.get_content("example")
        if factoid_content == None:
            factoid_content = "Factoid not found."

        return {
            "factoids": factoids,
            "factoids_json": json.dumps(factoids),
            "factoid_content": json.dumps(factoid_content),
            "factoid_name": json.dumps("new")
        }

    @aiohttp_jinja2.template('factoids/index.html')
    async def factoid(self, request):
        factoid_name = request.match_info["name"]
        logger.info("User %s requesting factoid %s", peer_data(request), factoid_name)

        factoids = self.factoids.list_of()
        factoid_content = self.factoids.get_content(factoid_name)
        if factoid_content == None:
            factoid_content = "Factoid not found."

        return {
            "factoids": factoids,
            "factoids_json": json.dumps(factoids),
            "factoid_content": json.dumps(self.factoids.get_content(factoid_name)),
            "factoid_name": json.dumps(factoid_name)
        }
        
    async def factoid_test(self, request):
        factoids = self.factoids.list_of()
        post_data = await request.post()

        testing_client = TestingChannelClient(self.client.global_store_path)

        logger.info("Running test command %s for %s", post_data['content'], peer_data(request))
        output = await testing_client.run_testing_command(post_data['content'])
        logger.info("Finished running test")

        return web.json_response(output)

    async def factoid_save(self, request):
        factoid_name = request.match_info["name"]
        post_data = await request.post()

        logger.info("Factoid %s saved by %s", factoid_name, peer_data(request))

        return web.json_response({
            "success": self.factoids.set_content(factoid_name, post_data['content'])
        })