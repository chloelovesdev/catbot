import aiohttp
from aiohttp import web
import aiohttp_jinja2, jinja2

import os
import json
import logging
import asyncio

from catbot.clients import TestingChannelClient
from catbot.managers import FileBasedFactoidManager

from python_json_config import ConfigBuilder

logger = logging.getLogger(__name__)

def request_ip(request):
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
        self.global_store_path = self.client.global_store_path

        self.app = web.Application(middlewares=[self.error_middleware])
        self.app.router.add_routes([
            web.get('/', self.index),
            web.get('/factoid/{name}', self.factoid),
            web.post('/factoid/{name}/save', self.factoid_save),
            web.post('/test', self.factoid_test),
            web.get('/manage/{bot_id}', self.manage_dashboard),
            web.get('/manage/{bot_id}/output', self.manage_output_websocket),
            web.get('/manage/{bot_id}/start', self.manage_start),
            web.get('/manage/{bot_id}/stop', self.manage_stop),
            web.get('/manage/{bot_id}/modules', self.manage_modules),
            web.post('/manage/{bot_id}/modules/update', self.manage_modules_update),
            web.get('/manage/{bot_id}/trust', self.manage_trust),
            web.post('/manage/{bot_id}/trust/update', self.manage_trust_update),
            web.get('/manage/{bot_id}/auth', self.manage_auth),
            web.post('/manage/{bot_id}/auth/update', self.manage_auth_update),
            web.get('/manage/{bot_id}/cron', self.manage_cron),
            web.post('/manage/{bot_id}/cron/update', self.manage_cron_update),
            web.static('/static', static_path)
        ])

        templates_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "templates")
        templates_path = os.path.realpath(templates_path)
        logger.info("Templates folder: %s", templates_path)

        self.factoids = FileBasedFactoidManager(self.global_store_path)
        self.open_sockets = {}

        aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader(templates_path))

    async def start(self):
        logger.info("Attempting to start management server")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', 8080) #TODO: configurable port and bind address
        await site.start()
        
    async def stop(self):
        logger.info("Stopping management server")
        await self.runner.cleanup()

    @web.middleware
    async def error_middleware(self, request, handler):
        try:
            response = await handler(request)
            if response.status != 404:
                return response
            message = response.message
        except web.HTTPException as ex:
            if ex.status != 404:
                raise
            message = ex.reason

        return aiohttp_jinja2.render_template('404.html', request, {})

    @aiohttp_jinja2.template('factoids/index.html')
    async def index(self, request):
        logger.info("User %s requesting index", request_ip(request))
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
        logger.info("User %s requesting factoid %s", request_ip(request), factoid_name)

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

        logger.info("Running test command %s for %s", post_data['content'], request_ip(request))
        output = await testing_client.run_testing_command(post_data['content'])
        logger.info("Finished running test")

        return web.json_response(output)

    async def factoid_save(self, request):
        factoid_name = request.match_info["name"]
        post_data = await request.post()

        logger.info("Factoid %s saved by %s", factoid_name, request_ip(request))

        return web.json_response({
            "success": self.factoids.set_content(factoid_name, post_data['content'])
        })

    @aiohttp_jinja2.template('manager/dashboard.html')
    async def manage_dashboard(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("User %s requesting manage dashboard for %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)

        return {
            "bot_id_json": json.dumps(bot_id),
            "bot_id": bot_id,
            "running": bot_id in self.client.processes
        }

    async def manage_output_websocket(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("Creating WebSocket for bot %s ip %s", bot_id, request_ip(request))
        self.check_valid_bot(bot_id)

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        if bot_id in self.open_sockets:
            self.open_sockets[bot_id] += [ws]
        else:
            self.open_sockets[bot_id] = [ws]

        if bot_id in self.client.last_x_messages.keys():
            for message in self.client.last_x_messages[bot_id]:
                await ws.send_str(message)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.CLOSE or msg.type == aiohttp.WSMsgType.CLOSED_FRAME:
                self.open_sockets[bot_id].remove(ws)
                break
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error('ws connection closed with exception %s', ws.exception())
                break
        
        self.open_sockets[bot_id].remove(ws)
        return ws

    async def manage_stop(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("%s requested to stop %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)
        success = False

        if bot_id in self.client.processes:
            self.client.processes[bot_id].terminate()
            if bot_id in self.open_sockets.keys():
                for bot_id, sockets in self.open_sockets.items():
                    for ws in sockets:
                        await ws.send_str("Bot process stopped.")

            success = True

        return web.json_response({
            "success": success
        })
    
    async def manage_start(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("%s requested to start %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)
        
        bots = self.client.bot_config.bots.to_dict()
        if bots[bot_id]['active'] == False:
            bots[bot_id]['active'] = True
            self.client.bot_config.update("bots", bots)
            self.client.save_config()

        success = True
        if bot_id in self.client.processes:
            success = False
        else:
            if bot_id in self.open_sockets.keys():
                for bot_id, sockets in self.open_sockets.items():
                    for ws in sockets:
                        await ws.send_str("Bot process starting.")
            asyncio.ensure_future(self.client.setup_bot(bot_id))

        return web.json_response({
            "success": success
        })

    def get_bot_store_path(self, bot_id):
        bot_id = bot_id.replace(".", "").replace("\\", "").replace("/", "")
        return os.path.realpath(os.path.join(self.global_store_path, bot_id))

    def get_bot_config_path(self, bot_id):
        return os.path.realpath(os.path.join(self.get_bot_store_path(bot_id), "config.json"))

    def get_bot_devices_path(self, bot_id):
        return os.path.realpath(os.path.join(self.get_bot_store_path(bot_id), "devices.json"))
    
    def get_config_for_bot(self, bot_id):
        config_path = self.get_bot_config_path(bot_id)

        if os.path.exists(config_path):
            return ConfigBuilder().parse_config(config_path)
        else:
            return None

    def get_all_modules(self):
        path_to_modules = os.path.realpath(os.path.join(os.path.dirname(__file__), "modules"))
        result = []

        for potential_module in os.listdir(path_to_modules):
            full_path = os.path.join(path_to_modules, potential_module)
            if os.path.isfile(full_path):
                result += [potential_module]
                
        return result

    def check_valid_bot(self, bot_id):
        if not bot_id in self.client.bot_config.bots:
            raise web.HTTPNotFound()
    
    def save_config(self, bot_id, config):
        config_as_json = json.dumps(config.to_dict(), indent=4)

        # save it to a file
        config_file = open(self.get_bot_config_path(bot_id), "w")
        config_file.write(config_as_json)
        config_file.close()

    @aiohttp_jinja2.template('manager/modules.html')
    async def manage_modules(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("User %s requesting module management for %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)

        bot_config = self.get_config_for_bot(bot_id)
        if bot_config == None:
            logger.warning("User %s tried to request a bot that doesn't exist (%s)", request_ip(request), bot_id)
            raise web.HTTPNotFound()

        all_modules = self.get_all_modules()
        module_states = {}
        
        all_enabled = False
        if bot_config.modules == None:
            all_enabled = True
        
        for module in all_modules:
            if all_enabled:
                module_states[module] = True
            else:
                module_states[module] = True if module in bot_config.modules else False

        return {
            "bot_id": bot_id,
            "modules": module_states,
            "all_enabled": all_enabled,
            "saved": "saved" in request.query
        }

    async def manage_modules_update(self, request):
        bot_id = request.match_info["bot_id"]
        post_data = await request.post()
        self.check_valid_bot(bot_id)

        bot_config = self.get_config_for_bot(bot_id)

        if "all_enabled" in post_data:
            bot_config.update("modules", None)
            self.save_config(bot_id, bot_config)
        else:
            modules_enabled = []
            for module in post_data:
                modules_enabled.append(module)
            bot_config.update("modules", modules_enabled)
            self.save_config(bot_id, bot_config)

        logger.info("Modules saved for %s by %s", bot_id, request_ip(request))
        raise web.HTTPFound(location=f"/manage/{bot_id}/modules?saved=1")

    @aiohttp_jinja2.template('manager/trust.html')
    async def manage_trust(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("User %s requesting trusted devices for %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)

        user_with_devices = {}
        devices_path = self.get_bot_devices_path(bot_id)
        
        if os.path.exists(devices_path):
            devices_file = open(self.get_bot_devices_path(bot_id))
            user_with_devices = json.loads(devices_file.read())
            devices_file.close()

        bot_config = self.get_config_for_bot(bot_id)

        return {
            "bot_id": bot_id,
            "user_with_devices": user_with_devices,
            "trust_state": bot_config.trust.to_dict() if bot_config.trust else None,
            "saved": "saved" in request.query
        }

    async def manage_trust_update(self, request):
        bot_id = request.match_info["bot_id"]
        post_data = await request.post()
        self.check_valid_bot(bot_id)

        bot_config = self.get_config_for_bot(bot_id)

        if "trust_all" in post_data:
            bot_config.update("trust", None)
            self.save_config(bot_id, bot_config)
        else:
            new_trust_state = {}

            for checked in post_data:
                if checked.startswith("trust_all_"):
                    user_to_trust = checked[len("trust_all_"):]
                    new_trust_state[user_to_trust] = None
                elif "[" in checked and "]" in checked:
                    checked_split = checked.split("[")

                    user_to_trust = checked_split[0]
                    device_to_trust = checked_split[1].split("]")[0]
                    if user_to_trust in new_trust_state:
                        new_trust_state[user_to_trust] += [device_to_trust]
                    else:
                        new_trust_state[user_to_trust] = [device_to_trust]

            bot_config.update("trust", new_trust_state)
            self.save_config(bot_id, bot_config)

        logger.info("Trusted devices saved for %s by %s", bot_id, request_ip(request))
        raise web.HTTPFound(location=f"/manage/{bot_id}/trust?saved=1")

    @aiohttp_jinja2.template('manager/auth.html')
    async def manage_auth(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("User %s requesting authentication settings for %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)

        main_config = self.client.bot_config
        bot_config = self.get_config_for_bot(bot_id)
        uses_defaults = bot_config.server.user_id == main_config.server.user_id

        homeserver = main_config.server.url
        user_id = main_config.server.user_id
        password = main_config.server.password

        if not uses_defaults:
            homeserver = bot_config.server.url
            user_id = bot_config.server.user_id
            password = bot_config.server.password

        if password == main_config.server.password:
            password = "haha nice try"

        return {
            "bot_id": bot_id,
            "uses_defaults": uses_defaults,
            "homeserver": homeserver,
            "user_id": user_id,
            "password": password,
            "saved": "saved" in request.query
        }

    async def manage_auth_update(self, request):
        bot_id = request.match_info["bot_id"]
        post_data = await request.post()
        self.check_valid_bot(bot_id)

        main_config = self.client.bot_config
        bot_config = self.get_config_for_bot(bot_id)

        if "defaults" in post_data or post_data["user_id"] == main_config.server.user_id:
            bot_config.update("server.url", main_config.server.url)
            bot_config.update("server.user_id", main_config.server.user_id)
            bot_config.update("server.password", main_config.server.password)
            self.save_config(bot_id, bot_config)
        else:
            bot_config.update("server.url", post_data["homeserver"])
            bot_config.update("server.user_id", post_data["user_id"])
            bot_config.update("server.password", post_data["password"])
            self.save_config(bot_id, bot_config)
            
        logger.info("User %s updating authentication settings for %s", request_ip(request), bot_id)

        raise web.HTTPFound(location=f"/manage/{bot_id}/auth?saved=1")
    
    @aiohttp_jinja2.template('manager/cron.html')
    async def manage_cron(self, request):
        bot_id = request.match_info["bot_id"]
        logger.info("User %s requesting scheduler for %s", request_ip(request), bot_id)
        self.check_valid_bot(bot_id)

        bot_config = self.get_config_for_bot(bot_id)
        existing_tasks = bot_config.cron if bot_config.cron else []
        tasks = []

        for x in range(5):
            if len(existing_tasks) > x:
                tasks += [ existing_tasks[x] ]
            else:
                tasks += [{
                    "command": "",
                    "interval": ""
                }]

        return {
            "bot_id": bot_id,
            "tasks": tasks,
            "saved": "saved" in request.query
        }

    async def manage_cron_update(self, request):
        bot_id = request.match_info["bot_id"]
        post_data = await request.post()
        self.check_valid_bot(bot_id)

        bot_config = self.get_config_for_bot(bot_id)
        new_tasks = []

        for x in range(1, 6):
            new_tasks.append({
                "command": post_data[f"task{x}[command]"],
                "interval": post_data[f"task{x}[interval]"]
            })

        bot_config.update("cron", new_tasks)
        self.save_config(bot_id, bot_config)
        logger.info("User %s updating scheduler settings for %s", request_ip(request), bot_id)

        raise web.HTTPFound(location=f"/manage/{bot_id}/cron?saved=1")