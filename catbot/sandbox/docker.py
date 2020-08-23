import aiodocker

import uuid
import shlex
import io
import time
import tarfile

import dateutil.parser

class DockerManager:
    def __init__(self):
        self.docker = aiodocker.Docker()

    def get_new_uuid(self):
        return "catbot-" + str(uuid.uuid4())

    async def run(self, image, command, stdin="", files=[], limits={}):
        try:
            await self.docker.images.inspect(image)
        except DockerError as e:
            if e.status == 404:
                await self.docker.pull(image)
            else:
                raise e

        return await DockerSandbox(
                    manager=self,
                    image=image,
                    limits=limits
                ).run(
                    command=command,
                    stdin=stdin,
                    files=files
                )

class DockerSandbox:
    def __init__(self, manager, image, limits, working_directory="/sandbox"):
        self.manager = manager
        self.image = image
        self.limits = limits
        self.working_directory = working_directory

        self.container_name = manager.get_new_uuid()

        self.log = None
        self.container = None

    async def destroy(self):
        pass

    # epicbox.sandboxes._write_files
    async def __write_files(self, files):
        files_written = []
        mtime = int(time.time())
        tarball_fileobj = io.BytesIO()

        with tarfile.open(fileobj=tarball_fileobj, mode='w') as tarball:
            for file in files:
                if not file.get('name') or not isinstance(file['name'], str):
                    continue

                content = file.get('content', b'')
                file_info = tarfile.TarInfo(name=file['name'])
                file_info.size = len(content)
                file_info.mtime = mtime
                tarball.addfile(file_info, fileobj=io.BytesIO(content))
                files_written.append(file['name'])

        write_result = await self.container.put_archive(self.working_directory, tarball_fileobj.getvalue())
        return write_result, files_written

    # epicbox.utils.inspect_exited_container_state
    async def inspect(self):
        data = await self.container.show()
        started_at = dateutil.parser.parse(data['State']['StartedAt'])
        finished_at = dateutil.parser.parse(data['State']['FinishedAt'])
        duration = finished_at - started_at
        duration_seconds = duration.total_seconds()
        if duration_seconds < 0:
            duration_seconds = -1

        return {
            'exit_code': data['State']['ExitCode'],
            'duration': duration_seconds,
            'oom_killed': data['State'].get('OOMKilled', False),
        }

    async def run(self, command, stdin, files=[]):
        print(f"[{self.container_name}] Creating container with command '{command}'")

        # https://docs.docker.com/engine/api/v1.24/
        self.container = await self.manager.docker.containers.create_or_replace(
                config = {
                    'Cmd': shlex.split(command),
                    'Image': self.image,
                    'WorkingDir': self.working_directory,
                    "AttachStdin": True,
                    "AttachStdout": True,
                    "AttachStderr": True,
                    "Tty": False,
                    "NetworkDisabled": self.limits['networking_disabled'],
                    "HostConfig": {
                        "Memory": self.limits['memory'] * 1024 * 1024, # bytes
                        "MemorySwap": self.limits['memory_swap'] * 1024 * 1024, # bytes
                        "CpuQuota": self.limits['cpu_quota'] * 1000000, # microseconds
                        "OomKillDisable": False,
                        "Privileged": False,
                        "PidsLimit": self.limits['processes'],
                        "Ulimits": [
                            {"Name": "cpu", "Soft": self.limits['ulimits']['cpu'], "Hard": self.limits['ulimits']['cpu']},
                            {"Name": "fsize", "Soft": self.limits['ulimits']['fsize'], "Hard": self.limits['ulimits']['fsize']},
                        ]
                    }
                },
                name=self.container_name,
            )

        await self.__write_files(files)

        try:
            print(f"Opening websocket")
            ws = await self.container.websocket(stdin=True, stdout=True, stderr=True, stream=True)

            print(f"Starting container")
            await self.container.start()

            resp = await ws.receive()
            await ws.close()

            print(f"Awaiting log")
            self.log = await self.container.log(stdout=True, stderr=True)
            self.state = await self.inspect()
        except Exception as e:
            print(f"Error occurred")
            raise e
        finally:
            print(f"Removing container")
            await self.container.delete(force=True)

        return self