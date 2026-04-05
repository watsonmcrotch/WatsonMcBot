import re
import logging
import asyncio
import anthropic
from threading import Thread
from pathlib import Path
from elevenlabs import ElevenLabs
import requests
import time
from typing import Optional, Dict
import os
from pydub import AudioSegment
import simpleaudio as sa
from services.tts_queue import TTSQueue, play_audio_file_async
from config import BASE_DIR

class BitAlert:
    def __init__(self, bot, send_companion_event):
        self.bot = bot
        self.send_companion_event = send_companion_event
        self.tts_queue = TTSQueue()

        self.base_dir = BASE_DIR
        self.video_dir = self.base_dir / 'overlays' / 'assets' / 'videos'

        self.govee_api_key = os.getenv('GOVEE_API_KEY')
        self.govee_device_id = os.getenv('GOVEE_DEVICE_ID')
        self.govee_device_id_2 = os.getenv('GOVEE_DEVICE_ID_2')
        self.govee_sku = os.getenv('GOVEE_SKU', 'H6006')
        self.claude = bot.claude
        self.tts_client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
        
        self.govee_url = 'https://developer-api.govee.com/v1/devices/control'
        self.govee_headers = {
            'Govee-API-Key': self.govee_api_key,
            'Content-Type': 'application/json'
        }
        
        self.light_blue_rgb = {"r": 173, "g": 216, "b": 240}
        self.dark_orange_rgb = {"r": 255, "g": 140, "b": 0}
        self.purple_rgb = {"r": 200, "g": 0, "b": 255}
        self.orange_rgb = {"r": 255, "g": 150, "b": 0}

    def clean_cheer_message(self, message: str) -> str:
        if not message:
            return ""
            
        cheer_pattern = r'^\w+\d+\s*'
        cleaned_message = re.sub(cheer_pattern, '', message)
        return cleaned_message.strip()

    def play_sound(self, file_path: str, volume: float = 1.0):
        try:
            audio = AudioSegment.from_file(file_path)
            adjusted_audio = audio - (1 - volume) * 30
            
            temp_wav = f"{file_path}_temp.wav"
            adjusted_audio.export(temp_wav, format="wav")
            
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            play_obj.wait_done()
            
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

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
                return response.status_code == 200
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(send_to_device, self.govee_device_id, "Device 1")
                future2 = executor.submit(send_to_device, self.govee_device_id_2, "Device 2")
                
                success_count = 0
                if future1.result():
                    success_count += 1
                if future2.result():
                    success_count += 1
                    
            return success_count > 0
            
        except Exception as e:
            logging.error(f"Error setting bits alert light color: {e}")
            return False

    async def flash_lights_100_plus(self):
        try:
            await asyncio.to_thread(self.set_light_color, self.orange_rgb)
            await asyncio.sleep(1)
            await asyncio.to_thread(self.set_light_color, self.purple_rgb)
        except Exception as e:
            logging.error(f"Error flashing lights for 100+ bits: {e}")

    async def flash_lights_1000_plus(self):
        try:
            await asyncio.to_thread(self.set_light_color, self.light_blue_rgb)
            await asyncio.sleep(0.5)
            await asyncio.to_thread(self.set_light_color, self.dark_orange_rgb)
            await asyncio.sleep(1)
            await asyncio.to_thread(self.set_light_color, self.purple_rgb)
        except Exception as e:
            logging.error(f"Error flashing lights for 1000+ bits: {e}")

    async def generate_tts(self, text: str) -> bool:
        try:
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="pNInz6obpgDQGcFmaJgB", 
                output_format="mp3_44100_128",
                text=text,
                model_id="eleven_multilingual_v2"
            )

            audio_data = b''
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_data += chunk
            
            temp_path = self.base_dir / 'sounds' / 'bit_alert_tts.mp3'
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            return True
                
        except Exception as e:
            logging.error(f"Error generating TTS: {e}")
            return False

    def get_video_path(self, bits: int) -> str:
        if bits == 1:
            return "assets/videos/1 bit.webm"
        elif 2 <= bits <= 9:
            return f"assets/videos/{bits} bits.webm"
        elif bits == 69:
            return "assets/videos/69 Bits Alert.webm"
        elif 10 <= bits <= 99:
            return "assets/videos/10 - 99 Bits Alert.webm"
        elif 100 <= bits <= 999:
            return "assets/videos/100 - 999 Bits Alert.webm"
        else:
            return "assets/videos/1000 Plus Bits Alert.webm"

    async def trigger(self, username: str, bits: int, message: str = ""):
        try:
            if not hasattr(self, "_last_trigger"):
                self._last_trigger = {}
            
            current_time = time.time()
            trigger_key = f"{username}_{bits}"
            
            if trigger_key in self._last_trigger:
                if current_time - self._last_trigger[trigger_key] < 5:
                    logging.info(f"Ignoring duplicate bit alert for {username} ({bits} bits)")
                    return
        
            self._last_trigger[trigger_key] = current_time
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            # Trigger WatsonOS browser overlay bits alert
            if hasattr(self.bot, 'overlay_manager'):
                asyncio.create_task(self.bot.overlay_manager.trigger_bits_alert(username, bits))

            video_path = self.get_video_path(bits)
            
            await self.send_companion_event('custom_video', {
                'video_path': video_path,
                'type': 'bit_alert',
                'width': '1920px',
                'height': '1080px',
                'position': {
                    'top': '0',
                    'left': '0'
                }
            })

            await asyncio.sleep(3)

            if bits >= 100:
                if bits >= 1000:
                    asyncio.create_task(self.flash_lights_1000_plus())
                else:
                    asyncio.create_task(self.flash_lights_100_plus())

            if bits >= 10:
                await asyncio.sleep(0.2)
                await self.send_companion_event('text-overlay', {
                    'content': f'{display_name} cheered {bits} bits!',
                    'style': {
                        'fontFamily': 'Montserrat ExtraBold',
                        'fontSize': '60px',
                        'color': 'white',
                        'textShadow': '4px 4px 6px rgba(0, 0, 0, 0.6)',
                        'position': 'absolute'
                    },
                    'position': {
                        'bottom': '220px',
                        'right': '220px'
                    },
                    'animateIn': 'fadeIn',
                    'animateOut': 'fadeOut',
                    'duration': 4000
                })

                await asyncio.sleep(1)
                
                cleaned_message = self.clean_cheer_message(message)
                tts_text = cleaned_message if cleaned_message else f"{display_name} cheered {bits} bits!"

                if await self.generate_tts(tts_text):
                    audio_path = self.base_dir / 'sounds' / 'bit_alert_tts.mp3'

                    async def play_bits_tts():
                        await play_audio_file_async(str(audio_path), 0.9)

                    await self.tts_queue.add_tts(f"bits_{username}_{bits}", play_bits_tts)

            char_limit = 30 if bits <= 10 else (
                80 if bits <= 100 else (
                160 if bits <= 500 else (
                400 if bits >= 1000 else 300
            )))

            prompt = f"""You are a hype bot who gives custom thank-yous for users that cheer bits, tailored to the user and scaling as the number of bits increases. 
            Keep responses fun and varied with adult humour, and try to avoid repetition. Make the user feel appreciated while ensuring grammar and punctuation are always correct.

            Guidelines:
            - Use British English spelling and grammar
            - Keep responses natural and conversational
            - Use gender-neutral pronouns
            - Acknowledge 69 bits with innuendo
            - CRITICAL: Your response must be under {char_limit} characters!
            - For small amounts (1-10 bits), keep it brief and simple
            - For larger amounts, you can be more elaborate and enthusiastic
            - Scale enthusiasm with bit amount

            User: {display_name}
            Bits: {bits}"""

            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                temperature=0.7,
                system="You are a hype bot that gives enthusiastic, custom thank-yous for bit cheers while keeping responses varied and appropriate in length.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            chat_message = str(response.content[0].text)[:char_limit].strip()
            
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                await channel.send(chat_message)

        except Exception as e:
            logging.error(f"Error processing bit alert: {e}")