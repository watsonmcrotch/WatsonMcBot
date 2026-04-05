import random
import asyncio
from threading import Thread
import simpleaudio as sa
import logging

class JamieRedeem:
    def __init__(self, send_companion_event):
        self.send_companion_event = send_companion_event
        self.video_path = "assets/videos/jamie.webm"

        self.screen_width = 1920
        self.screen_height = 1080
        
        self.original_width = 800
        self.original_height = 800
        
        self.scale = 0.6
        self.video_width = int(self.original_width * self.scale)
        self.video_height = int(self.original_height * self.scale)

    def get_random_position(self):
        padding = 30
        
        max_x = max(0, self.screen_width - self.video_width - padding)
        max_y = max(0, self.screen_height - self.video_height - padding)
        
        x = random.randint(padding, max_x) if max_x > padding else padding
        y = random.randint(padding, max_y) if max_y > padding else padding
                
        return {
            'left': f'{x}px',
            'top': f'{y}px'
        }

    async def trigger_companion_event(self):
        await asyncio.sleep(0.2)
        await self.send_companion_event('reaction', {'type': 'look-up-left', 'intensity': 1.2})
        await asyncio.sleep(9)
        await self.send_companion_event('reaction', {'type': 'cool', 'intensity': 1.2})

    async def process_jamie_redeem(self, channel):
        try:
            asyncio.create_task(self.trigger_companion_event())
            
            position = self.get_random_position()
            await self.send_companion_event('custom_video', {
                'video_path': self.video_path,
                'type': 'jamie',
                'duration': 9000,
                'width': f'{self.video_width}px',
                'height': f'{self.video_height}px',
                'position': position,
                'animateIn': 'fadeIn',
                'animateOut': 'fadeOut',
                'volume': '0.3'
            })
            
        except Exception as e:
            logging.error(f"Error in really cool guy redeem: {e}")