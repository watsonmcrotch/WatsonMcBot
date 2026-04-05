import sys
import os
from datetime import datetime
import logging
import asyncio
from typing import Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BOT_NAME, CHANNEL_NAME

class BotState:
    def __init__(self):
        self._state = {
            'bot_name': BOT_NAME,
            'channel_name': CHANNEL_NAME,
            'twitch_connected': False,
            'discord_connected': False,
            'spotify_connected': False,
            'current_game': "Unknown Game",
            'current_song': None,
            'error_count': 0,
            'last_activity': None,
            '_running': False
        }
        self._lock = asyncio.Lock()
        self._output_queue = None

    def set_output_queue(self, queue):
        self._output_queue = queue

    async def async_update(self, **kwargs) -> None:
        async with self._lock:
            try:
                changed = False
                for key, value in kwargs.items():
                    if key in self._state and self._state[key] != value:
                        self._state[key] = value
                        changed = True
                        logging.info(f"Updated {key} to {value}")
                
                if changed and self._output_queue:
                    status_message = {
                        "type": "status",
                        "data": self.get_status(),
                        "timestamp": datetime.now().isoformat()
                    }
                    await self._output_queue.put(status_message)
                    
            except Exception as e:
                logging.error(f"Error in async_update: {e}")
                raise

    def update(self, **kwargs) -> None:
        try:
            changed = False
            for key, value in kwargs.items():
                if key in self._state and self._state[key] != value:
                    self._state[key] = value
                    changed = True
                    logging.info(f"Updated {key} to {value}")
            
            if changed:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop.is_running():
                    loop.create_task(self._schedule_update())
                else:
                    loop.run_until_complete(self._schedule_update())
                    
        except Exception as e:
            logging.error(f"Error in update: {e}")
            raise

    async def _schedule_update(self) -> None:
        if not self._output_queue:
            logging.warning("No output queue set, skipping update")
            return

        async with self._lock:
            try:
                status_message = {
                    "type": "status",
                    "data": self.get_status(),
                    "timestamp": datetime.now().isoformat()
                }
                loop = asyncio.get_running_loop()
                if self._output_queue._loop is not loop:
                    self._output_queue = asyncio.Queue()
                await self._output_queue.put(status_message)
            except Exception as e:
                logging.error(f"Error in _schedule_update: {e}")
                raise

    def get_status(self) -> dict:
        return self._state.copy()

    def force_broadcast(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._schedule_update())
        except Exception as e:
            logging.error(f"Error in force_broadcast: {e}")

bot_state = BotState()