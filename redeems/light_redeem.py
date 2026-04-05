import os
import logging
import asyncio
import anthropic
import requests
import threading
from threading import Timer
from typing import Dict

class LightController:
    def __init__(self, db_manager, send_companion_event=None, claude=None):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.govee_api_key = os.getenv('GOVEE_API_KEY')
        self.govee_device_id = os.getenv('GOVEE_DEVICE_ID')
        self.govee_device_id_2 = os.getenv('GOVEE_DEVICE_ID_2')
        self.govee_sku = os.getenv('GOVEE_SKU', 'H6006')
        self.claude = claude or anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        
        self.govee_url = 'https://developer-api.govee.com/v1/devices/control'
        self.govee_headers = {
            'Govee-API-Key': self.govee_api_key,
            'Content-Type': 'application/json'
        }
        
        self.default_rgb = {'r': 200, 'g': 0, 'b': 255}
        
        self.reset_timer = None

    def _schedule_reset(self):
        if self.reset_timer:
            self.reset_timer.cancel()
        
        self.reset_timer = Timer(300, self._reset_color)
        self.reset_timer.daemon = True
        self.reset_timer.start()

    def _reset_color(self):
        try:
            self.set_light_color(self.default_rgb)
            logging.info("Light color reset to default")
        except Exception as e:
            logging.error(f"Error resetting light color: {e}")

    def set_light_color(self, color_rgb: Dict[str, int]) -> bool:
        try:
            import concurrent.futures
            
            logging.info(f"Attempting to set light color to: {color_rgb}")
            
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
                logging.info(f"{device_name} ({device_id}): Status {response.status_code}")
                return response.status_code == 200
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(send_to_device, self.govee_device_id, "Device 1")
                future2 = executor.submit(send_to_device, self.govee_device_id_2, "Device 2")
                
                success_count = 0
                if future1.result():
                    success_count += 1
                if future2.result():
                    success_count += 1
                    
            logging.info(f"Light control result: {success_count}/2 devices responded successfully")
            return success_count > 0
            
        except Exception as e:
            logging.error(f"Error setting light color: {e}")
            return False

    async def process_color_request(self, channel, username: str, message: str) -> None:
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            rgb_response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=1000,
                temperature=0.8,
                system="You are a color interpreter that converts messages into RGB values, you understand adult humour and will use context clues to provide accurate colors regardless of the abstractness of a message.",
                messages=[{
                    "role": "user",
                    "content": f"Respond to this message with an appropriate RGB value in the format: 'R: <value>, G: <value>, B: <value>'. Do not provide any extra text or explanations.\n\nThe message in this case is \"{message}\""
                }]
            )

            rgb_text = rgb_response.content[0].text.strip()
            logging.info(f"Claude RGB response: '{rgb_text}'")

            try:
                rgb_values = [int(val.split(': ')[1]) for val in rgb_text.split(', ')]
                color_rgb = {"r": rgb_values[0], "g": rgb_values[1], "b": rgb_values[2]}
                logging.info(f"Parsed RGB values: {color_rgb}")
            except Exception as parse_error:
                logging.error(f"Error parsing RGB values from '{rgb_text}': {parse_error}")
                await channel.send(f"Sorry {display_name}, I couldn't understand the color format!")
                return
            if await asyncio.to_thread(self.set_light_color, color_rgb):
                self._schedule_reset()
                
                confirmation_response = await asyncio.to_thread(
                    self.claude.messages.create,
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1500,
                    temperature=0.7,
                    system="You are an assistant that responds with a helpful yet witty message in response to a users request to change the color of Watson's lights.",
                    messages=[{
                        "role": "user",
                        "content": f"Your job is to work alongside another assistant who provides RGB values based on a users message. You will confirm that the lights were changed to a color. You will understand the RGB value was interpreted from the users message which in some instances will be very abstract, and you will respond with a short witty message to confirm the successful color change was applied to Watson's lights. \n\nUsername = {display_name}\n\nMessage = {message}\n\nRGB Value = {rgb_text}\n\nStrict instructions:\n- Limit your response to 150 characters.\n- Respond in British English for spelling and grammar.\n- British cultural references are cringe, avoid over use of them.\n- Do not use emojis, non-standard characters, or additional formatting.\n- Your humour needs to be crude, clever, and adult as this is an 18+ only environment. Remember, it's not the user's lights that are changing, they're changing Watson's lights."
                    }]
                )
                
                await channel.send(confirmation_response.content[0].text.strip())
            else:
                await channel.send(f"Sorry {display_name}, something went wrong with the lights!")

        except Exception as e:
            logging.error(f"Error processing color request: {e}")
            await channel.send(f"Sorry {display_name}, something went wrong!")

    def cleanup(self):
        if self.reset_timer:
            self.reset_timer.cancel()