import epicbox

from catbot import module

class Sandbox(module.Module):
    @module.setup
    async def setup(self, event):
        epicbox.configure({
            'python': {
                'docker_image': 'python:3.6.5-alpine',
                #'user': 'sandbox',
                #'read_only': True,
                'network_disabled': False,
            }
        })

        return [
            "python"
        ]

    @module.command("python", help="Executes python code.")
    async def on_cmd_python(self, event):
        files = [{'name': 'main.py', 'content': event.body.encode("utf-8")}]
        limits = {'cputime': 20, 'memory': 64}
        result = epicbox.run('python', 'python3 main.py', files=files, limits=limits)

        print(len(result['stdout']))
        if "stderr" in result and result["stderr"] != b'':
            await event.reply("An error occurred while trying to run module\n\n" + result["stderr"].decode("utf-8"))
        elif "stdout" in result and result["stdout"] != b'':
            await event.reply(result["stdout"].decode("utf-8"))
        elif result["timeout"]:
            await event.reply("Command timed out")
        elif result["oom_killed"]:
            await event.reply("Command used too much memory")
        elif "stdout" in result:
            await event.reply("Command did not output anything.")
            