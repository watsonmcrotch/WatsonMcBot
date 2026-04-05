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

class StoriesHandler:
    def __init__(self, db_manager, send_companion_event):
        
        self.tts_queue = TTSQueue()
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        
        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        
        if not self.elevenlabs_key:
            logging.error("ELEVENLABS_API_KEY is not set in environment variables.")
            
        self.tts_client = ElevenLabs(api_key=self.elevenlabs_key)
        
        self.tts_output = str(BASE_DIR / 'sounds' / 'story_response.mp3')
        self.background_music = str(BASE_DIR / 'sounds' / 'scarysong.mp3')
        
        self.active_playback = None
        self.crossfade_duration = 1000

    def get_audio_duration(self, file_path: str) -> float:
        try:
            audio = AudioSegment.from_file(file_path)
            return len(audio)
        except Exception as e:
            logging.error(f"Error getting audio duration: {e}")
            return 0

    def play_sound_with_fade(self, sound_path: str, volume: float = 1.0, fade_in: int = 0, 
                           fade_out: int = 0, duration: int = None):
        try:
            audio = AudioSegment.from_file(sound_path)
            adjusted_audio = audio - (1 - volume) * 30

            if fade_in:
                adjusted_audio = adjusted_audio.fade_in(fade_in)

            if fade_out:
                if duration:
                    fade_start = min(len(adjusted_audio), duration) - fade_out
                    if fade_start > 0:
                        adjusted_audio = adjusted_audio.fade(
                            start=fade_start,
                            duration=fade_out,
                            from_gain=0,
                            to_gain=-120
                        )
                else:
                    adjusted_audio = adjusted_audio.fade_out(fade_out)

            if duration:
                adjusted_audio = adjusted_audio[:duration]

            temp_wav = f"{sound_path}_{time.time()}_temp.wav"
            adjusted_audio.export(temp_wav, format="wav")

            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            
            if self.active_playback:
                self.active_playback.stop()
            self.active_playback = play_obj

            def cleanup():
                play_obj.wait_done()
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

            cleanup_thread = Thread(target=cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()

        except Exception as e:
            logging.error(f"Error playing sound with fade: {e}")

    async def generate_tts(self, text: str) -> bool:
        try:
            logging.info("Generating TTS for text: %s", text)
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="nPczCjzI2devNBz1zQrb",
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

    async def process_story_redeem(self, channel, username: str, story_text: str):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username) if user_context else username

            if not story_text or len(story_text.strip()) == 0:
                await channel.send(f"{display_name}, I need some text to read!")
                return

            if await self.generate_tts(story_text):
                tts_duration = self.get_audio_duration(self.tts_output)
                if tts_duration == 0:
                    tts_duration = 10000

                bg_music_duration = tts_duration + 8000
                fade_out_duration = 5000

                async def play_story_with_bg():
                    try:
                        # Start background music
                        music_thread = Thread(
                            target=self.play_sound_with_fade,
                            args=(self.background_music,),
                            kwargs={
                                'volume': 0.5,
                                'fade_out': fade_out_duration,
                                'duration': bg_music_duration
                            }
                        )
                        music_thread.daemon = True
                        music_thread.start()
                    except Exception as e:
                        logging.error(f"Error playing background music: {e}")

                    # Wait for intro timing
                    await asyncio.sleep(3)

                    # Play the TTS
                    try:
                        await play_audio_file_async(self.tts_output, 1.0)
                    except Exception as e:
                        logging.error(f"Error playing TTS response: {e}")

                await self.tts_queue.add_tts(f"story_{username}", play_story_with_bg)
                    
            else:
                await channel.send(f"Sorry {display_name}, I couldn't generate the speech...")
                    
        except Exception as e:
            logging.error(f"Error processing story redeem: {e}")
            await channel.send(f"Something went wrong with the TTS generation, {username}...")