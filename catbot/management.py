import aiohttp
from aiohttp import web
import os
import aiohttp_jinja2, jinja2

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
        return os.listdir(self.factoids_path)

    @aiohttp_jinja2.template('factoids/index.html')
    async def index(self, request):
        return {
            "factoids": self.get_factoids()
        }

    @aiohttp_jinja2.template('factoids/index.html')
    async def factoid(self, request):
        return {
            "factoids": self.get_factoids(),
            "factoid": "test"
        }