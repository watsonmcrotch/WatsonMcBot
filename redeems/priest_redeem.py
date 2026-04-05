import logging
import asyncio
from threading import Thread
import simpleaudio as sa
from pydub import AudioSegment
import anthropic
import os
from pathlib import Path
from elevenlabs import ElevenLabs
from twitchio.ext import commands
import time
from services.tts_queue import TTSQueue, play_audio_file_async
from config import BASE_DIR

class PriestHandler:
    def __init__(self, db_manager, send_companion_event):
        
        self.tts_queue = TTSQueue()
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        
        self.claude_key = os.getenv('CLAUDE_API_KEY')
        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        
        if not self.claude_key:
            logging.error("CLAUDE_API_KEY is not set in environment variables.")
        if not self.elevenlabs_key:
            logging.error("ELEVENLABS_API_KEY is not set in environment variables.")
        
        anthropic.api_key = self.claude_key
        
        self.tts_client = ElevenLabs(api_key=self.elevenlabs_key)
        
        self.confession_chime = str(BASE_DIR / 'sounds' / 'confession.mp3')
        self.priest_msg = str(BASE_DIR / 'sounds' / 'priest_msg.mp3')
        self.tts_output = str(BASE_DIR / 'sounds' / 'priest_response.mp3')
        
        self.active_playback = None

    def clean_text(self, text: str) -> str:
        return text.replace('{', '').replace('}', '').replace('`', '')

    def play_sound(self, sound_path: str, volume: float = 1.0):
        try:
            audio = AudioSegment.from_file(sound_path)
            adjusted_audio = audio - (1 - volume) * 30

            temp_wav = f"{sound_path}_{time.time()}_temp.wav"
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
            
    async def generate_claude_response(self, display_name: str, confession: str) -> str:
        system_prompt = f"""You are a clueless but enthusiastic Twitch stream priest who knows nothing about actual religion.
        Address the user as "{display_name}". They are confessing something. Your job is to vindicate / forgive them no matter what,
        coming up with hilariously bad justifications for their sins. Keep responses under 330 characters.
        No emoji's and no asterisks to emphasis actions like *adjusts glasses*. Be entertaining."""

        try:
            client = anthropic.Client(api_key=self.claude_key)
            message = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=550,
                temperature=0.8,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Confession from {display_name}: {confession}"}
                ]
            )
            return message.content[0].text
            
        except Exception as e:
            logging.error(f"Error generating Claude response: {e}")
            return None

    async def generate_tts(self, text: str) -> bool:
        try:
            logging.info("Generating TTS for text: %s", text)
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="NOpBlnGInO9m6vDvFkFC",
                output_format="mp3_44100_128",
                text=text,
                model_id="eleven_v3"
            )

            audio_data = b''
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_data += chunk
            
            with open(self.tts_output, 'wb') as f:
                f.write(audio_data)
            
            logging.info("Successfully generated TTS audio")
            return True
                
        except Exception as e:
            logging.error(f"Error generating TTS: {e}")
            return False

    async def process_priest_redeem(self, channel, username: str, confession: str):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username) if user_context else username

            if not confession or len(confession.strip()) == 0:
                await channel.send(f"🙏 {display_name}, I need something to forgive you for!")
                return

            await self.send_companion_event('reaction', {'type': 'confession', 'intensity': 1.2})

            claude_response = await self.generate_claude_response(display_name, confession)

            if claude_response is None:
                error_message = f"🙏 The confession hotline is experiencing technical difficulties, {display_name}..."
                await channel.send(error_message)
                return

            if await self.generate_tts(claude_response):
                await channel.send(f"{claude_response}")

                async def play_priest_with_sounds():
                    # Play confession chime
                    await asyncio.to_thread(self.play_sound, self.confession_chime, 0.6)

                    # Play priest message sound
                    await asyncio.to_thread(self.play_sound, self.priest_msg, 0.8)

                    # Play the TTS
                    await play_audio_file_async(self.tts_output, 1.0)

                await self.tts_queue.add_tts(f"priest_{username}", play_priest_with_sounds)

            else:
                await channel.send(f"It seems the Hotline is experiencing technical difficulties, {display_name}...")
                    
        except Exception as e:
            logging.error(f"Error processing priest redeem: {e}")
            await channel.send(f"🙏 Jesus's magic has failed momentarily, {username}...")