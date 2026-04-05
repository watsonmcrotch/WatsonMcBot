import asyncio
import logging
from typing import Optional


class OverlayManager:
    """Coordinates WatsonOS browser overlay alerts via WebSocket broadcasts."""

    def __init__(self, bot):
        self.bot = bot

    async def _broadcast(self, event_type: str, data: dict):
        try:
            from services.websocket_server import ws_manager
            await ws_manager.broadcast({'type': event_type, 'data': data})
        except Exception as e:
            logging.error(f"OverlayManager broadcast error: {e}")

    async def trigger_follow_alert(self, username: str):
        await self._broadcast('watsonos_follow', {
            'username': username
        })

    async def trigger_bits_alert(self, username: str, bits: int):
        await self._broadcast('watsonos_bits', {
            'username': username,
            'bits': bits
        })

    async def trigger_raid_alert(self, username: str, viewer_count: int):
        await self._broadcast('watsonos_raid', {
            'username': username,
            'viewer_count': viewer_count
        })

    async def trigger_sub_alert(self, username: str, tier: str, is_resub: bool, cumulative_months: int):
        await self._broadcast('watsonos_sub', {
            'username': username,
            'tier': tier,
            'is_resub': is_resub,
            'cumulative_months': cumulative_months
        })

    async def trigger_intro_transition(self):
        await self._broadcast('watsonos_intro', {})

    async def trigger_giftsub_alert(self, gifter: str, total_subs: int):
        await self._broadcast('watsonos_giftsub', {
            'gifter': gifter,
            'total_subs': total_subs
        })

    def sync_taskbar_scene(self, scene_name: str):
        try:
            asyncio.ensure_future(self._broadcast('watsonos_scene', {
                'scene': scene_name
            }))
        except Exception as e:
            logging.error(f"Error syncing taskbar scene: {e}")
