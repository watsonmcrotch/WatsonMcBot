import anthropic
import requests
import time
import asyncio
import logging
from pathlib import Path
import os

class FollowAlert:
    def __init__(self, bot, send_companion_event):
        self.bot = bot
        self.govee_api_key = os.getenv('GOVEE_API_KEY')
        self.govee_device_id = os.getenv('GOVEE_DEVICE_ID')
        self.govee_device_id_2 = os.getenv('GOVEE_DEVICE_ID_2')
        self.govee_sku = os.getenv('GOVEE_SKU', 'H6006')
        self.send_companion_event = send_companion_event
        self.video_path = "assets/videos/follow-alert.webm"
        self.govee_url = 'https://developer-api.govee.com/v1/devices/control'
        self.govee_headers = {
            'Govee-API-Key': self.govee_api_key,
            'Content-Type': 'application/json'
        }
        self.teal_rgb = {'r': 0, 'g': 255, 'b': 242}
        self.purple_rgb = {'r': 200, 'g': 0, 'b': 255}
        self.claude = bot.claude

    async def trigger(self, username):
        try:
            # Resolve display name for overlay text
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            # Trigger WatsonOS browser overlay alert if available
            if hasattr(self.bot, 'overlay_manager'):
                asyncio.create_task(self.bot.overlay_manager.trigger_follow_alert(username, display_name=display_name))

            await asyncio.gather(
                self.send_overlay_alert(username),
                self.trigger_lights(),
                self.send_chat_message(username),
                self.send_companion_event('reaction', {'type': 'heart', 'intensity': 1.2})
            )
        except Exception as e:
            logging.error(f"Error in follow alert for {username}: {e}")

    async def send_overlay_alert(self, username):
        """Legacy video overlay removed — WatsonOS browser overlay handles visuals."""
        pass

    async def trigger_lights(self):
        try:
            for _ in range(2):
                await asyncio.to_thread(self.set_light_color, self.teal_rgb)
                await asyncio.sleep(0.5)
                await asyncio.to_thread(self.set_light_color, self.purple_rgb)
                await asyncio.sleep(1)
            await asyncio.to_thread(self.set_light_color, self.purple_rgb)
        except Exception as e:
            logging.error(f"Error controlling lights: {e}")

    def set_light_color(self, color_rgb):
        try:
            import concurrent.futures
            
            def send_to_device(device_id, device_name):
                payload = {
                    "device": device_id,
                    "model": self.govee_sku,
                    "cmd": {
                        "name": "color",
                        "value": color_rgb
                    }
                }
                response = requests.put(self.govee_url, headers=self.govee_headers, json=payload)
                return response.status_code
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(send_to_device, self.govee_device_id, "Device 1")
                future2 = executor.submit(send_to_device, self.govee_device_id_2, "Device 2")
                
                status1 = future1.result()
                status2 = future2.result()
                
                if status1 == 200:
                    return status1
                elif status2 == 200:
                    return status2
                else:
                    return 400
            
        except Exception as e:
            logging.error(f"Error setting follow alert light color: {e}")
            return 500

    async def send_chat_message(self, username):
        try:
            prompt = f"""You are a hype bot who thanks people that just followed my livestream, you tailor your response to the user.
    You will keep your responses concise and sincere. '{username}' just followed.
    Thank them and attempt to make a witty pun with the name '{username}' if it is appropriate.
    Keep your response within 100 characters."""

            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system="You are a hype bot who thanks people that just followed my livestream, you tailor your response to the user. Keep your responses concise and sincere.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            chat_message = str(response.content[0].text).strip()

            if len(chat_message) > 100:
                chat_message = chat_message[:100].rstrip()
            
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                await channel.send(chat_message)
            else:
                logging.error("Could not get channel for follow alert message")
            
        except Exception as e:
            logging.error(f"Error generating/sending chat message: {e}")
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                await channel.send(f"Thanks for following, {username}!")