import inspect
import os
import importlib
import logging

from catbot.events import ReplyBufferingEvent

logger = logging.getLogger(__name__)

class ModuleManager:
    def __init__(self, client):
        self.client = client
        self.modules = self.load(self.client.bot_config.modules)# maybe TODO: make this work without a client

    async def send_to(self, module_obj, event, buffer_replies=True, return_dicts=False):
        results = []

        for method_name, method_obj in inspect.getmembers(module_obj, predicate=inspect.ismethod):
            # do not include any __ functions, they are module internals
            if not "__" in method_name:
                method_result = method_obj(event)

                if not method_result == None:
                    result = await method_result

                    # normally module setups returns lists of commands they handle
                    if result != None and isinstance(result, list):
                        results += result
                    # some modules return dicts in their setup handlers
                    # this is used to know which commands eat all input and do not use redirection
                    elif result != None and isinstance(result, dict) and return_dicts:# TODO
                        return result
        
        return results

    async def send_to_all(self, event, buffer_replies=False, return_dicts=False):
        results = {}

        # create a buffering event
        buffering_event = ReplyBufferingEvent(self.client, event, buffer_replies=buffer_replies)
        
        # loop through all loaded modules
        for name, module in self.modules.items():
            results[module] = await self.send_to(module, buffering_event, return_dicts=return_dicts)
        
        return results

    def load(self, modules_enabled=None):
        result = {}

        path_to_commands = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "modules"))
        logger.info("Found path to modules: %s", path_to_commands)
        modules_loaded = 0

        for fname in os.listdir(path_to_commands):
            path = os.path.join(path_to_commands, fname)
            
            if os.path.isdir(path):
                # skip directories
                continue

            if modules_enabled:
                if not fname in modules_enabled:
                    logger.info("Skipping module %s, module is disabled", path)
                    continue
                
            logger.info("Loading module from %s", path)

            command_name = os.path.splitext(fname)[0]

            # import module's spec from file
            spec = importlib.util.spec_from_file_location("catbot.modules." + command_name, path)
            imported_module = importlib.util.module_from_spec(spec)
            # load it into python
            spec.loader.exec_module(imported_module)

            # instantiate the class with the same name as the file
            for class_name, class_obj in inspect.getmembers(imported_module, inspect.isclass):
                if class_name.lower() == command_name.lower().replace("_", "").replace("-", ""):
                    module = class_obj(self.client)
                    result[command_name] = module
                    modules_loaded += 1

        logger.info("%d modules loaded.", modules_loaded)
        return result