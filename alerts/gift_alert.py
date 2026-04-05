import aiohttp
import logging
import anthropic
import asyncio
import os
import requests
from datetime import datetime

class GiftSubAlert:
    def __init__(self, bot, send_companion_event):
        self.bot = bot
        self.send_companion_event = send_companion_event
        self.claude = bot.claude
        self.recent_gifts = {}
        self.COOLDOWN = 10
        self.single_gift_video = "assets/videos/giftsubs.webm"
        self.mass_gift_video = "assets/videos/mass_giftsubs.webm"
        self.govee_api_key = os.getenv('GOVEE_API_KEY')
        self.govee_device_id = os.getenv('GOVEE_DEVICE_ID')
        self.govee_device_id_2 = os.getenv('GOVEE_DEVICE_ID_2')
        self.govee_sku = os.getenv('GOVEE_SKU', 'H6006')
        self.govee_url = 'https://developer-api.govee.com/v1/devices/control'
        self.govee_headers = {
            'Govee-API-Key': self.govee_api_key,
            'Content-Type': 'application/json'
        }
        self.white_rgb = {'r': 255, 'g': 255, 'b': 255}
        self.lightblue_rgb = {'r': 153, 'g': 204, 'b': 255}
        self.purple_rgb = {'r': 200, 'g': 0, 'b': 255}

    async def trigger(self, gifter_username: str, total_subs: int, recipient_username: str = None, is_anonymous: bool = False):
        try:
            current_time = datetime.now()
            if recipient_username:
                gift_key = f"{gifter_username}_{recipient_username}"
                if gift_key in self.recent_gifts:
                    last_time = self.recent_gifts[gift_key]
                    if (current_time - last_time).total_seconds() < self.COOLDOWN:
                        logging.info(f"Skipping duplicate gift sub alert for {gift_key}")
                        return
                self.recent_gifts[gift_key] = current_time

            if not is_anonymous:
                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, gifter_username)
                gifter_display = user_context.get('nickname', gifter_username)
            else:
                gifter_display = "anonymous"

            recipient_display = None
            if recipient_username:
                rc_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, recipient_username)
                recipient_display = rc_context.get('nickname', recipient_username)

            # Trigger WatsonOS browser overlay giftsub alert
            if hasattr(self.bot, 'overlay_manager'):
                asyncio.create_task(self.bot.overlay_manager.trigger_giftsub_alert(gifter_display, total_subs))

            await self.set_light_color(self.white_rgb)
            await asyncio.sleep(0.5)
            await self.set_light_color(self.lightblue_rgb)
            await asyncio.sleep(1.0)
            await self.set_light_color(self.purple_rgb)

            chat_message = await self.generate_gift_sub_message(
                gifter_display=gifter_display,
                recipient_display=recipient_display,
                total_subs=total_subs,
                is_anonymous=is_anonymous
            )
                
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                await channel.send(chat_message)

        except Exception as e:
            logging.error(f"Error processing gift sub alert: {e}")
            logging.exception("Full traceback:")

    async def generate_gift_sub_message(self, gifter_display: str, recipient_display: str, total_subs: int, is_anonymous: bool) -> str:
        try:
            if total_subs == 1 and recipient_display:
                user_line = f"{gifter_display} gifted a sub to {recipient_display}"
            elif total_subs == 1:
                user_line = f"{gifter_display} gifted a sub"
            else:
                user_line = f"{gifter_display} gifted {total_subs} subs"
            prompt = f"Create a short playful chat message about this gift sub event: {user_line}, limit 250 chars."
            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=1000,
                temperature=0.7,
                system="You are a Twitch bot generating fun, thankful, witty messages for gift sub events, using adult humour when appropriate.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return str(response.content[0].text)[:250].strip()
        except Exception as e:
            logging.error(f"Error generating gift sub chat message: {e}")
            return f"{gifter_display} just dropped some gift sub love!"

    async def set_light_color(self, color_rgb: dict) -> bool:
        try:
            success_count = 0
            
            session = self.bot.http_session
            payload_1 = {
                "device": self.govee_device_id,
                "model": self.govee_sku,
                "cmd": {"name": "color", "value": color_rgb}
            }
            payload_2 = {
                "device": self.govee_device_id_2,
                "model": self.govee_sku,
                "cmd": {"name": "color", "value": color_rgb}
            }

            task1 = session.put(self.govee_url, headers=self.govee_headers, json=payload_1)
            task2 = session.put(self.govee_url, headers=self.govee_headers, json=payload_2)

            responses = await asyncio.gather(task1, task2, return_exceptions=True)

            for response in responses:
                if hasattr(response, 'status') and response.status == 200:
                    success_count += 1

            return success_count > 0
            
        except Exception as e:
            logging.error(f"Error setting gift alert light color: {e}")
            return False
