import logging
import asyncio
from threading import Thread
import simpleaudio as sa
from pydub import AudioSegment
from elevenlabs import ElevenLabs
import os
from pathlib import Path
import time
from services.tts_queue import TTSQueue, play_audio_file_async
from config import BASE_DIR

class WatsonHandler:
    def __init__(self, db_manager, send_companion_event):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.tts_queue = TTSQueue()

        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')

        if not self.elevenlabs_key:
            logging.error("ELEVENLABS_API_KEY is not set in environment variables.")

        self.tts_client = ElevenLabs(api_key=self.elevenlabs_key)
        self.tts_output = str(BASE_DIR / 'sounds' / 'watsontts.mp3')

    def play_sound(self, sound_path: str, volume: float = 1.0):
        try:
            audio = AudioSegment.from_file(sound_path)
            adjusted_audio = audio - (1 - volume) * 30
            
            temp_wav = f"{sound_path}_{time.time()}_temp.wav"
            adjusted_audio.export(temp_wav, format="wav")
            
            def play_and_cleanup():
                try:
                    wave_obj = sa.WaveObject.from_wave_file(temp_wav)
                    play_obj = wave_obj.play()
                    play_obj.wait_done()
                finally:
                    try:
                        os.remove(temp_wav)
                    except Exception:
                        pass

            play_thread = Thread(target=play_and_cleanup)
            play_thread.daemon = True
            play_thread.start()

        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    async def generate_tts(self, text: str) -> bool:
        try:
            logging.info("Generating TTS for text: %s", text)
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="oDeeTwS8uAbF2gT91oAM",
                output_format="mp3_44100_128",
                text=text,
                model_id="eleven_v3",           
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

    async def process_watsontts_redeem(self, channel, username: str, story_text: str):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username) if user_context else username

            if not story_text or len(story_text.strip()) == 0:
                await channel.send(f"{display_name}, I need some text to read!")
                return

            if await self.generate_tts(story_text):
                async def play_watson_tts():
                    await play_audio_file_async(self.tts_output, 1.0)

                await self.tts_queue.add_tts(f"watson_{username}", play_watson_tts)
                    
            else:
                await channel.send(f"Sorry {display_name}, I couldn't generate the speech...")
                    
        except Exception as e:
            logging.error(f"Error processing story redeem: {e}")
            await channel.send(f"Something went wrong with the TTS generation, {username}...")