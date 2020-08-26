import aiodocker
import aiohttp

import uuid
import shlex
import io
import time
import tarfile
import asyncio
import logging

import dateutil.parser

logger = logging.getLogger(__name__)

class DockerManager:
    def __init__(self):
        self.docker = aiodocker.Docker()

    def get_new_uuid(self):
        return "catbot-" + str(uuid.uuid4())

    async def get_new_volume(self):
        name = self.get_new_uuid()
        logger.info("Attempting to create Docker volume %s", name)
        volume = await self.docker.volumes.create({
            "Name": name
        })

        logger.info("Successfully created Docker volume %s", name)
        return volume

    async def run(self, image, command, persistent_volume=None, stdin=b"", files=[], limits={}):
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
                limits=limits,
                persistent_volume=persistent_volume
            ).run(
                command=command,
                stdin=stdin,
                files=files
            )

class DockerSandbox:
    def __init__(self, manager, image, limits, persistent_volume=None, working_directory="/sandbox"):
        self.manager = manager
        self.image = image
        self.limits = limits
        self.working_directory = working_directory
        self.persistent_volume = persistent_volume

        self.container_name = manager.get_new_uuid()

        self.log = None
        self.container = None
        self.output = None

        logger.info("[%s] DockerSandbox initialized with image %s", self.container_name, self.image)

    async def destroy(self):
        pass

    # epicbox.sandboxes._write_files
    async def __write_files(self, files):
        logger.info("[%s] Writing files to container", self.container_name)

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
        logger.info("[%s] Inspecting container", self.container_name)
        data = await self.container.show()
        logger.info("[%s] State data retrieved", self.container_name)

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
        self.output = b''

        binds = []
        if self.persistent_volume != None:
            binds = [f"{self.persistent_volume.name}:{self.working_directory}:rw"]

        logger.info("[%s] Creating Docker container with image %s", self.container_name, self.image)

        # https://docs.docker.com/engine/api/v1.24/
        self.container = await self.manager.docker.containers.create_or_replace(
                config = {
                    'Cmd': shlex.split(command),
                    'Image': self.image,
                    'WorkingDir': self.working_directory,
                    "AttachStdin": True,
                    "AttachStdout": True,
                    "AttachStderr": True,
                    "OpenStdin": True,
                    "StdinOnce": True,
                    "Tty": False,
                    "User": self.limits['user'],
                    "NetworkDisabled": self.limits['networking_disabled'],
                    "HostConfig": {
                        "Binds": binds,
                        "Memory": self.limits['memory'] * 1024 * 1024, # bytes
                        "MemorySwap": self.limits['memory_swap'] * 1024 * 1024, # bytes
                        "CpuQuota": self.limits['cpu_quota'] * 1000000, # microseconds
                        "OomKillDisable": False,
                        "Privileged": False,
                        "PidsLimit": self.limits['processes'],
                        "Ulimits": [
                            {"Name": "cpu", "Soft": self.limits['ulimits']['cpu'], "Hard": self.limits['ulimits']['cpu']},
                            {"Name": "fsize", "Soft": self.limits['ulimits']['fsize'] * 1024, "Hard": self.limits['ulimits']['fsize'] * 1024},
                        ]
                    }
                },
                name=self.container_name,
            )

        if len(files) > 0:
            await self.__write_files(files)
        else:
            logger.warning("[%s] We didn't write any files to container.", self.container_name)

        try:
            stdin_ws = await self.container.websocket(stdin=True, stdout=False, stderr=False, stream=True)
            stdouterr_ws = await self.container.websocket(stdin=False, stdout=True, stderr=True, stream=True)

            logger.info("[%s] Starting container", self.container_name)
            await self.container.start()

            logger.info("[%s] Writing stdin data into container", self.container_name)
            await stdin_ws.send_bytes(stdin)
            await stdin_ws.close()

            logger.info("[%s] Beginning container receive loop", self.container_name)
            while True:
                msg = await stdouterr_ws.receive()
                
                if msg.type == aiohttp.WSMsgType.BINARY:
                    self.output += msg.data
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    await stdouterr_ws.close()
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise Exception("Docker websocket error")
                    break

            logger.info("[%s] Container receive loop finished", self.container_name)
            self.log = await self.container.log(stdout=True, stderr=True)
            self.state = await self.inspect()
        except Exception as e:
            raise e
        finally:
            await self.container.delete(force=True)

        logger.info("")
        logger.info("[%s] Command: %s", self.container_name, command)
        if self.state and 'duration' in self.state:
            logger.info("[%s] Duration: %f", self.container_name, self.state['duration'])
        if self.state and 'exit_code' in self.state:
            logger.info("[%s] Exit code: %d", self.container_name, self.state['exit_code'])

        return self