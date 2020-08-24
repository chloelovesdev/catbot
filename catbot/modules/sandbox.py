import epicbox

from catbot import module
from catbot.sandbox.docker import DockerManager

class Sandbox(module.Module):
    @module.setup
    async def setup(self, event):
        self.manager = DockerManager()

        return [
            "python",
            "java"
        ]
    
    def __reply_sandbox(self, event, sandbox):
        if sandbox.log:
            event.reply("".join(sandbox.log))
        elif sandbox.state['exit_code'] == 0 and sandbox.log != None:
            event.reply("Command finished successfully with no output.")
        elif sandbox.state['oom_killed']:
            event.reply("Sandbox ran out of memory")
        elif sandbox.state['exit_code'] != 0:
            event.reply("Error, non-zero exit code: " + str(sandbox.state['exit_code']))
        elif sandbox.log == None:
            event.reply("Error, sandbox output was never set")

    @module.command("python", help="Sandboxed python.")
    async def on_cmd_python(self, event):
        sandbox = await self.manager.run(
            image='python:3.6.5-alpine',
            command="python3 main.py",
            files=[{
                "name": "main.py",
                "content": event.body.encode("utf-8")
            }],
            stdin=event.stdin_data,
            limits={
                "memory": 64, # MB
                "user": "root",
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

    @module.command("java", help="Sandboxed java.")
    async def on_cmd_java(self, event):
        workdir_volume = await self.manager.get_new_volume()

        try:
            sandbox = await self.manager.run(
                image='catbot/java/16-slim:latest',
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
                    "processes": 10,
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