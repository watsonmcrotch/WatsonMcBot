import asyncio
import logging
import anthropic
import requests
import os 
from pathlib import Path
import aiohttp
from threading import Thread
from typing import Optional, Dict

class RaidAlert:
    def __init__(self, bot, db_manager, send_companion_event):
        self.bot = bot
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.claude = bot.claude

        self.video_path = "assets/videos/raid.webm"
        
        self.text_position = {
            'top': '450px',
            'left': '300px'
        }
        
        self.govee_api_key = os.getenv('GOVEE_API_KEY')
        self.govee_device_id = os.getenv('GOVEE_DEVICE_ID')
        self.govee_device_id_2 = os.getenv('GOVEE_DEVICE_ID_2')
        self.govee_sku = os.getenv('GOVEE_SKU', 'H6006')
        
        self.govee_url = 'https://developer-api.govee.com/v1/devices/control'
        self.govee_headers = {
            'Govee-API-Key': self.govee_api_key,
            'Content-Type': 'application/json'
        }
        
        self.red_rgb = {'r': 255, 'g': 0, 'b': 0}
        self.blue_rgb = {'r': 0, 'g': 0, 'b': 255}
        self.purple_rgb = {'r': 200, 'g': 0, 'b': 255}

    def set_light_color(self, color_rgb: Dict[str, int]) -> bool:
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
                logging.info(f"Raid alert {device_name}: Status {response.status_code}")
                return response.status_code == 200
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(send_to_device, self.govee_device_id, "Device 1")
                future2 = executor.submit(send_to_device, self.govee_device_id_2, "Device 2")
                
                success_count = 0
                if future1.result():
                    success_count += 1
                if future2.result():
                    success_count += 1
                    
            logging.info(f"Raid alert: {success_count}/2 devices responded successfully")
            return success_count > 0
            
        except Exception as e:
            logging.error(f"Error setting raid alert light color: {e}")
            return False

    async def flash_lights(self):
        try:
            logging.info("Starting raid alert light flash sequence")
            
            for i in range(2):
                logging.info(f"Flash {i+1} Setting to RED {self.red_rgb}")
                await asyncio.to_thread(self.set_light_color, self.red_rgb)
                await asyncio.sleep(1.5)

                logging.info(f"Flash {i+1} Setting to BLUE {self.blue_rgb}")
                await asyncio.to_thread(self.set_light_color, self.blue_rgb)
                await asyncio.sleep(1.5)

            logging.info("Flash sequence complete, waiting 10 seconds...")
            await asyncio.sleep(10)

            logging.info(f"Setting final color to PURPLE {self.purple_rgb}")
            final_result = await asyncio.to_thread(self.set_light_color, self.purple_rgb)
            logging.info(f"Final color set result: {final_result}")

            if not final_result:
                logging.info("Final color failed, retrying in 20 seconds...")
                await asyncio.sleep(20)
                retry_result = await asyncio.to_thread(self.set_light_color, self.purple_rgb)
                logging.info(f"Retry result: {retry_result}")
            
        except Exception as e:
            logging.error(f"Error flashing lights during raid: {e}")

    async def generate_raid_message(self, display_name: str, viewer_count: int) -> str:
        try:
            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=1000,
                temperature=0.8,
                system="You are a hype bot that gives super energetic, enthusiastic, custom thank-yous to users that raid the channel. Your goal is to make the raider feel appreciated and get chat excited!",
                messages=[{
                    "role": "user",
                    "content": f"Create an exciting raid welcome message for {display_name} who just raided with {viewer_count} viewers! Keep it under 50 characters."
                }]
            )
            
            return str(response.content[0].text)[:400]
            
        except Exception as e:
            logging.error(f"Error generating raid message: {e}")
            return f"Welcome raiders! Thank you so much for the raid {display_name}!"

    async def generate_shoutout_message(self, display_name: str, username: str, game: Optional[str] = None, title: Optional[str] = None) -> str:
        try:
            context = f"They were playing {game}" if game else ""
            context += f" with stream title: {title}" if title else ""
            
            prompt = (
                f"Create a personalized shoutout for {display_name}. {context}. "
                f"At the end of the message, include their Twitch URL as: https://twitch.tv/{username} "
                "Keep the total message under 400 characters and maintain the exact URL format provided. Don't use @"
            )
            
            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=1000,
                temperature=0.8,
                system="You are a bot creating a personalized shoutout message for a Twitch streamer who just raided. "
                       "Be enthusiastic and highlight their content! Make sure to preserve their exact Twitch URL at the end.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            return str(response.content[0].text)[:400]
            
        except Exception as e:
            logging.error(f"Error generating shoutout message: {e}")
            return f"Hey everyone! You should definitely check out {display_name} at twitch.tv/{username}!"

    async def get_raider_info(self, username: str) -> Dict:
        try:
            broadcaster_token = await self.bot.token_manager.get_token('broadcaster')
            headers = {
                'Client-ID': self.bot.broadcaster_client_id,
                'Authorization': f'Bearer {broadcaster_token}'
            }
            
            async with self.bot.http_session.get(
                f'https://api.twitch.tv/helix/users?login={username}',
                headers=headers
            ) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                if not data['data']:
                    return {}
                user_id = data['data'][0]['id']

            async with self.bot.http_session.get(
                f'https://api.twitch.tv/helix/channels?broadcaster_id={user_id}',
                headers=headers
            ) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                if not data['data']:
                    return {}
                return {
                    'game_name': data['data'][0].get('game_name'),
                    'title': data['data'][0].get('title')
                }
            
        except Exception as e:
            logging.error(f"Error getting raider info: {e}")
            return {}

    async def get_display_name(self, username: str) -> str:
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            return user_context.get('nickname', username)
        except Exception as e:
            logging.error(f"Error getting display name: {e}")
            return username

    async def trigger(self, username: str, viewer_count: int):
        try:
            display_name = await self.get_display_name(username)
            asyncio.create_task(self.flash_lights())

            # Trigger WatsonOS browser overlay raid alert
            if hasattr(self.bot, 'overlay_manager'):
                asyncio.create_task(self.bot.overlay_manager.trigger_raid_alert(username, viewer_count, display_name=display_name))

            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                raid_message = await self.generate_raid_message(display_name, viewer_count)
                await channel.send(raid_message)
                
                await asyncio.sleep(7)
                
                raider_info = await self.get_raider_info(username)
                shoutout_message = await self.generate_shoutout_message(
                    display_name=display_name,
                    username=username,
                    game=raider_info.get('game_name'),
                    title=raider_info.get('title')
                )
                await channel.send(shoutout_message)
                
                await asyncio.sleep(5)
                await channel.send(f"/shoutout {username}")
                
                await asyncio.sleep(10)
                await channel.send(f"Welcome in everyone! Hope you all enjoy the stream!")
                
        except Exception as e:
            logging.error(f"Error processing raid alert: {e}")