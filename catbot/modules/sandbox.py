import epicbox

from catbot import module
from catbot.sandbox.docker import DockerManager

class Sandbox(module.Module):
    @module.setup
    async def setup(self, event):
        self.manager = DockerManager()

        return [
            "python",
            "test"
        ]

    @module.command("python", help="Test python sandbox.")
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

        if sandbox.log:
            event.reply("".join(sandbox.log))
        
        if not sandbox.log:
            event.reply("Error occurred (log not set)")
        elif len(sandbox.log) == 0:
            event.reply("Sandbox output was empty.")
        elif sandbox.state['oom_killed']:
            event.reply("Sandbox ran out of memory")
        elif sandbox.state['exit_code'] != 0:
            event.reply("Error, non-zero exit code: " + sandbox.state['exit_code'])

        print(sandbox.state)