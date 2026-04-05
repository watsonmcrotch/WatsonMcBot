import logging
from datetime import datetime
from typing import Dict, Any

class DashboardBroadcaster:

    def __init__(self, ws_manager):
        self.ws_manager = ws_manager

    async def broadcast_log(self, level: str, message: str):
        try:
            await self.ws_manager.broadcast({
                'type': 'log',
                'level': level,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting log: {e}")

    async def broadcast_chat(self, username: str, message: str, color: str = '#FFFFFF'):
        try:
            await self.ws_manager.broadcast({
                'type': 'chat',
                'username': username,
                'message': message,
                'color': color,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting chat: {e}")

    async def broadcast_status(self, statuses: Dict[str, Any]):
        try:
            await self.ws_manager.broadcast({
                'type': 'status',
                'statuses': statuses,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting status: {e}")

    async def broadcast_stream_info(self, stream_info: Dict[str, Any]):
        try:
            await self.ws_manager.broadcast({
                'type': 'stream_info',
                **stream_info,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting stream info: {e}")

    async def broadcast_now_playing(self, song_info: Dict[str, str]):
        try:
            await self.ws_manager.broadcast({
                'type': 'now_playing',
                **song_info,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting now playing: {e}")

    async def broadcast_active_systems(self, systems: Dict[str, Any]):
        try:
            await self.ws_manager.broadcast({
                'type': 'active_systems',
                **systems,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error broadcasting active systems: {e}")

_broadcaster = None

def get_broadcaster(ws_manager=None):
    global _broadcaster
    if _broadcaster is None and ws_manager:
        _broadcaster = DashboardBroadcaster(ws_manager)
    return _broadcaster
