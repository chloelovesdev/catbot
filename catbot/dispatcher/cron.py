import pytimeparse
import asyncio
import time

from nio import RoomMessageText

class CronDispatcher:
    def __init__(self, client):
        self.client = client
        self.time_jump = 1
        self.time_limit = 3600
    
    async def start(self):
        second_counter = 0

        while True:
            if not self.client.has_setup:
                await asyncio.sleep(5)
                continue

            if second_counter == self.time_limit:
                second_counter = 0

            if self.client.bot_config.cron:
                for cron_task in self.client.bot_config.cron:
                    cron_command = cron_task['command']
                    cron_time = cron_task['interval'].strip()
                    parsed_cron_time = pytimeparse.parse(cron_time)

                    if (second_counter % parsed_cron_time) == 0:
                        print(f"Running cron command '{cron_command}'")

                        event = RoomMessageText.from_dict({
                                'room_id': self.client.bot_config.server.channel,
                                'type': 'm.room.message',
                                'content': {
                                    'msgtype': 'm.text',
                                    'body': cron_command
                                },
                                'event_id': 'cron',
                                'sender': self.client.bot_config.server.user_id,
                                'origin_server_ts': int(time.time())
                            })
                        self.client.command_dispatcher.queue.append(event)

            second_counter += self.time_jump
            await asyncio.sleep(self.time_jump)