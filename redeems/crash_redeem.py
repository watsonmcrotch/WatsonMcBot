import random
import asyncio
from threading import Thread
import simpleaudio as sa
import logging

class CrashRedeem:
    def __init__(self, send_companion_event):
        self.send_companion_event = send_companion_event
        self.video_path = "assets/videos/crash.webm"

        self.screen_width = 1920
        self.screen_height = 1080
        
        self.original_width = 1920
        self.original_height = 1080

    async def trigger_companion_event(self):
        await asyncio.sleep(1.0)
        await self.send_companion_event('reaction', {'type': 'look-up-left', 'intensity': 1.2})

    async def process_crash_redeem(self, channel):
        try:
            asyncio.create_task(self.trigger_companion_event())
            
            await self.send_companion_event('custom_video', {
                'video_path': self.video_path,
                'type': 'crash',
                'duration': 7000,
                'width': 1920,
                'height': 1080,
                'animateIn': 'fadeIn',
                'volume': 0.5,
            })
            
        except Exception as e:
            logging.error(f"Error in crash redeem: {e}")