import asyncio
import logging
from pathlib import Path
from threading import Thread
from pydub import AudioSegment
import simpleaudio as sa
from datetime import datetime
import discord
import os
from google import genai
from services.websocket_server import WEB_SERVER_URL
from config import BASE_DIR

class ImageRedeemHandler:
    def __init__(self, db_manager, discord_monitor, send_companion_event=None):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.discord_monitor = discord_monitor
        self.genai_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        self.base_dir = BASE_DIR
        self.assets_dir = self.base_dir / 'overlays' / 'assets'
        self.images_dir = self.assets_dir / 'images'
        self.sounds_dir = self.base_dir / 'sounds'
        
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        self.start_sound = str(self.sounds_dir / 'image_start.wav')
        self.complete_sound = str(self.sounds_dir / 'image_complete.wav')
        
        if not Path(self.start_sound).exists():
            logging.error(f"Start sound file not found: {self.start_sound}")
        if not Path(self.complete_sound).exists():
            logging.error(f"Complete sound file not found: {self.complete_sound}")
            
        self.discord_channel_id = int(os.getenv('DISCORD_CHANNEL_IMAGES')) if os.getenv('DISCORD_CHANNEL_IMAGES') else None

    def play_sound_threaded(self, sound_path: str, volume: float = 0.6):
        try:
            wave_obj = sa.WaveObject.from_wave_file(sound_path)
            play_obj = wave_obj.play()
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    async def play_sound_async(self, sound_path: str, volume: float = 0.6):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.play_sound_threaded, sound_path, volume)
        except Exception as e:
            logging.error(f"Error in play_sound_async: {e}")

    async def generate_image(self, prompt: str, save_path: Path) -> None:
        try:
            logging.info(f"Starting Gemini image generation with prompt: {prompt}")

            response = await asyncio.to_thread(
                self.genai_client.models.generate_content,
                model="gemini-3.1-flash-image-preview",
                contents=prompt,
                config={"response_modalities": ["IMAGE"]},
            )

            # Extract and save the generated image
            image_saved = False
            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    await asyncio.to_thread(image.save, str(save_path))
                    image_saved = True
                    break

            if not image_saved:
                raise Exception("No image was returned by the model")

            logging.info("Gemini image generation completed successfully")

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error in generate_image: {error_msg}")
            error_lower = error_msg.lower()
            if any(kw in error_lower for kw in ['safety', 'blocked', 'content policy', 'moderation', 'prohibited']):
                raise Exception("moderation_failed")
            elif "connection" in error_lower:
                raise Exception("connection_error")
            elif "timeout" in error_lower:
                raise Exception("timeout_error")
            raise

    async def share_to_discord(self, username: str, prompt: str, image_path: Path):
        try:
            message = f"**{username}**: *\"{prompt}\"*"
            
            if self.discord_channel_id is None:
                user = await self.discord_monitor.fetch_user(self.discord_monitor.discord_user_id)
                if user:
                    with open(image_path, 'rb') as file:
                        discord_file = discord.File(file, filename='image_output.png')
                        await user.send(content=message, file=discord_file)
                else:
                    logging.error(f"Could not find Discord user with ID {self.discord_monitor.discord_user_id}")
            else:
                channel = self.discord_monitor.get_channel(self.discord_channel_id)
                if channel:
                    with open(image_path, 'rb') as file:
                        discord_file = discord.File(file, filename='image_output.png')
                        await channel.send(content=message, file=discord_file)
                        
                        self.discord_monitor.creative_redeems.update_generation('image', {
                            'prompt': prompt,
                            'user': username,
                            'timestamp': datetime.now().isoformat()
                        })
                else:
                    logging.error(f"Could not find Discord channel with ID {self.discord_channel_id}")
        except Exception as e:
            logging.error(f"Error sharing to Discord: {e}")

    async def process_image_redeem(self, channel, username: str, prompt: str, user_color: str = "#FF69B4"):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            logging.info(f"Processing image redeem for {display_name}")
            
            try:
                await self.play_sound_async(self.start_sound, 0.5)
            except Exception as e:
                logging.error(f"Error playing start sound: {e}")

            if self.send_companion_event:
                await self.send_companion_event('reaction', {'type': 'paint', 'intensity': 1.0})

            unique_id = f"{int(datetime.now().timestamp())}_{os.urandom(4).hex()}"
            image_filename = f'image_output_{unique_id}.png'
            image_path = self.images_dir / image_filename
            web_path = f'/assets/images/{image_filename}'

            try:
                await self.generate_image(prompt, image_path)
            except Exception as e:
                error_message = str(e)
                error_responses = {
                    "moderation_failed": f"Sorry {display_name}, your prompt was flagged by content moderation. 🚫",
                    "invalid_prompt": f"Sorry {display_name}, that prompt wasn't quite right. Try rephrasing it! 🤔",
                    "connection_error": f"Sorry {display_name}, I'm having trouble connecting to the image service. Please try again! 🌐",
                    "timeout_error": f"Sorry {display_name}, the request timed out. The servers might be busy... ⏳",
                }
                await channel.send(error_responses.get(error_message, f"Sorry {display_name}, something went wrong with the image generation! Error: {error_message}"))
                return

            try:
                await self.play_sound_async(self.complete_sound, 0.5)
            except Exception as e:
                logging.error(f"Error playing complete sound: {e}")

            await asyncio.sleep(3)

            try:
                await asyncio.sleep(1)
                
                await asyncio.gather(
                    self.send_companion_event('show-image', {
                        'url': web_path,
                        'style': {
                            'position': 'absolute',
                            'top': '40px',
                            'left': '40px',
                            'width': '640px',
                            'height': '480px',
                            'borderRadius': '14px',
                            'shadow': '4px 4px 10px rgba(0,0,0,0.5)',
                            'margin': '0, 0, 20px, 0',
                        },
                        'animateIn': 'fadeIn',
                        'animateOut': 'fadeOut',
                        'duration': 30000,
                    }),
                    self.send_companion_event('text-overlay', {
                        'content': f'{display_name}',
                        'style': {
                            'fontFamily': 'Montserrat',
                            'fontWeight': '800',
                            'fontSize': '42px',
                            'textAlign': 'left',
                            'color': user_color,
                            'position': 'absolute',
                            'text-shadow': '1px 2px 2px rgba(0,0,0, 0.5',
                            'margin': '0, 0, 20px, 0',
                        },
                        'position': {
                            'top': '525px',
                            'left': '40px',
                        },
                        'animateIn': 'fadeIn',
                        'animateOut': 'fadeOut',
                        'duration': 30000,
                    }),
                    self.send_companion_event('text-overlay', {
                        'content': f'{prompt}',
                        'style': {
                            'fontFamily': 'Montserrat',
                            'fontWeight': '700',
                            'fontSize': '34px',
                            'textAlign': 'left',
                            'color': 'white',
                            'position': 'absolute',
                            'maxWidth': '1000px',
                            'text-shadow': '1px 2px 2px rgba(0,0,0, 0.5',
                        },
                        'position': {
                            'top': '580px',
                            'left': '40px',
                        },
                        'animateIn': 'fadeIn',
                        'animateOut': 'fadeOut',
                        'duration': 30000,
                    })
                )
            except Exception as e:
                logging.error(f"Error sending overlay event: {e}")

            try:
                await channel.send(f"Here's your AI masterpiece, {display_name}! 🎨")
                await self.share_to_discord(display_name, prompt, image_path)
            except Exception as e:
                logging.error(f"Error sharing to Discord: {e}")
                await channel.send(f"Sorry {display_name}, your image was generated but there was an error sharing it to Discord.")

        except Exception as e:
            logging.error(f"Unexpected error processing image redeem: {e}")
            await channel.send(f"Sorry {display_name}, an unexpected error occurred! Please try again later.")