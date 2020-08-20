import epicbox

from catbot.modules import module

class Sandbox(module.Module):
    @module.setup
    async def setup(self, event):
        PROFILES = {
            'gcc_compile': {
                'docker_image': 'stepik/epicbox-gcc:6.3.0',
                'user': 'root',
            },
            'gcc_run': {
                'docker_image': 'stepik/epicbox-gcc:6.3.0',
                # It's safer to run untrusted code as a non-root user (even in a container)
                'user': 'sandbox',
                'read_only': True,
                'network_disabled': False,
            },
        }

        return [
            "sandbox python"
        ]

    @module.command("sandbox python", help="Executes python code.")
    async def on_cmd_python(self, event):
        epicbox.configure(
            profiles=[
                epicbox.Profile('python', 'python:3.6.5-alpine')
            ]
        )

        files = [{'name': 'main.py', 'content': event.body.encode("utf-8")}]
        limits = {'cputime': 1, 'memory': 64}
        result = epicbox.run('python', 'python3 main.py', files=files, limits=limits)

        print(result)
        if "stderr" in result and result["stderr"] != b'':
            await self.bot.send_text("An error occurred while trying to run module\n\n" + stderr.decode("utf-8"))
        elif "stdout" in result and result["stdout"] != b'':
            await self.bot.send_text(result["stdout"].decode("utf-8"))
        elif "stdout" in result:
            await self.bot.send_text("Command did not output anything.")
            