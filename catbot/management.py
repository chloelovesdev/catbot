import aiohttp
from aiohttp import web
import os
import aiohttp_jinja2, jinja2
import json
from catbot.clients import TestingChannelClient

class ManagementServer:
    def __init__(self, client):
        static_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "static")
        static_path = os.path.realpath(static_path)
        print(f"Static folder: {static_path}")

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
        print(f"Templates folder: {templates_path}")

        self.factoids_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "storage", "factoids")
        self.factoids_path = os.path.realpath(self.factoids_path)
        print(f"Factoids folder: {self.factoids_path}")

        aiohttp_jinja2.setup(self.app,
            loader=jinja2.FileSystemLoader(templates_path))

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 8080)
        await site.start()
        
    async def stop(self):
        await self.runner.cleanup()

    def get_factoids(self):
        all_factoids = os.listdir(self.factoids_path)
        nonstate_factoids = []

        for factoid in all_factoids:
            if not factoid.startswith("state-"):
                nonstate_factoids.append(factoid)

        nonstate_factoids.sort()
        return nonstate_factoids

    def get_factoid(self, name):
        name = name.replace(".", "").replace("\\", "").replace("//", "")
        factoid_path = os.path.join(self.factoids_path, name)

        if os.path.exists(factoid_path):
            factoid_file = open(factoid_path)
            result = factoid_file.read()
            factoid_file.close()
            return result
        else:
            return "Factoid not found."

    def save_factoid(self, name, content):
        name = name.replace(".", "").replace("\\", "").replace("//", "")
        factoid_path = os.path.join(self.factoids_path, name)
        factoid_file = open(factoid_path, "w")
        factoid_file.write(content)
        factoid_file.close()
        return True

    @aiohttp_jinja2.template('factoids/index.html')
    async def index(self, request):
        factoids = self.get_factoids()

        return {
            "factoids": factoids,
            "factoids_json": json.dumps(factoids),
            "factoid_content": json.dumps(self.get_factoid("example")),
            "factoid_name": json.dumps("new")
        }

    @aiohttp_jinja2.template('factoids/index.html')
    async def factoid(self, request):
        factoids = self.get_factoids()

        return {
            "factoids": factoids,
            "factoids_json": json.dumps(factoids),
            "factoid_content": json.dumps(self.get_factoid(request.match_info["name"])),
            "factoid_name": json.dumps(request.match_info["name"])
        }
        
    async def factoid_test(self, request):
        factoids = self.get_factoids()
        post_data = await request.post()

        testing_client = TestingChannelClient(self.client.global_store_path)
        output = await testing_client.run_testing_command(post_data['content'])

        return web.json_response(output)

    async def factoid_save(self, request):
        post_data = await request.post()

        return web.json_response({
            "success": self.save_factoid(request.match_info["name"], post_data['content'])
        })