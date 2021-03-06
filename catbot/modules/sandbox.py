from catbot import module
from catbot.sandbox.docker import DockerManager

class Sandbox(module.Module):
    @module.setup
    async def setup(self, event):
        self.manager = DockerManager()

        return [
            "python",
            "java",
            "js",
            "php"
        ]
    
    def __reply_sandbox(self, event, sandbox):
        if isinstance(sandbox.output, bytes) and len(sandbox.output) != 0:
            event.reply(sandbox.output)
        elif sandbox.state['exit_code'] == 0 and (not isinstance(sandbox.output, bytes) or len(sandbox.output) == 0):
            event.reply("Command finished successfully with no output.")
        elif sandbox.state['oom_killed']:
            event.reply("Sandbox ran out of memory")
        elif sandbox.state['exit_code'] != 0:
            event.reply("Error, non-zero exit code: " + str(sandbox.state['exit_code']))
        elif not isinstance(sandbox.output, bytes):
            event.reply("Error, sandbox output was never set")

    @module.command("python", help="Python sandboxed with docker.")
    async def on_cmd_python(self, event):
        sandbox = await self.manager.run(
            image='catbot/python:3.7.9-slim',
            command="python3 main.py",
            files=[{
                "name": "main.py",
                "content": event.body.encode("utf-8")
            }],
            stdin=event.stdin_data,
            limits={
                "memory": 64, # MB
                "user": "sandbox",
                "memory_swap": 64, # MB
                "networking_disabled": False,
                "cpu_quota": 60, # seconds
                "processes": 5,
                "ulimits": {
                    "cpu": 20, # seconds
                    "fsize": 10 # MB
                }
            }
        )

        self.__reply_sandbox(event, sandbox)

    @module.command("php", help="PHP sandboxed with docker.")
    async def on_cmd_php(self, event):
        sandbox = await self.manager.run(
            image='catbot/php:cli-alpine',
            command="php main.php",
            files=[{
                "name": "main.php",
                "content": event.body.encode("utf-8")
            }],
            stdin=event.stdin_data,
            limits={
                "memory": 128, # MB
                "user": "sandbox",
                "memory_swap": 128, # MB
                "networking_disabled": False,
                "cpu_quota": 60, # seconds
                "processes": 5,
                "ulimits": {
                    "cpu": 20, # seconds
                    "fsize": 10 # MB
                }
            }
        )

        self.__reply_sandbox(event, sandbox)

    @module.command("js", help="node.js sandboxed with docker.")
    async def on_cmd_js(self, event):
        sandbox = await self.manager.run(
            image='catbot/node:stretch-slim',
            command="node main.js",
            files=[{
                "name": "main.js",
                "content": event.body.encode("utf-8")
            }],
            stdin=event.stdin_data,
            limits={
                "memory": 128, # MB
                "user": "sandbox",
                "memory_swap": 64, # MB
                "networking_disabled": False,
                "cpu_quota": 60, # seconds
                "processes": 20,
                "ulimits": {
                    "cpu": 20, # seconds
                    "fsize": 10 # MB
                }
            }
        )

        self.__reply_sandbox(event, sandbox)

    @module.command("java", help="Java 16 sandboxed with docker.")
    async def on_cmd_java(self, event):
        workdir_volume = await self.manager.get_new_volume()

        try:
            sandbox = await self.manager.run(
                image='catbot/java:16-slim',
                command="javac Factoid.java",
                persistent_volume=workdir_volume,
                files=[{
                    "name": "Factoid.java",
                    "content": event.body.encode("utf-8")
                }],
                stdin=event.stdin_data,
                limits={
                    "memory": 256, # MB
                    "memory_swap": 256, # MB
                    "networking_disabled": False,
                    "cpu_quota": 60, # seconds
                    "processes": 20,
                    "user": "sandbox",
                    "ulimits": {
                        "cpu": 20, # seconds
                        "fsize": 10 # MB
                    }
                }
            )

            if sandbox.state['exit_code'] == 0:
                sandbox = await sandbox.run("java Factoid", event.stdin_data)
                self.__reply_sandbox(event, sandbox)
            else:
                self.__reply_sandbox(event, sandbox)
        finally:
            await workdir_volume.delete()