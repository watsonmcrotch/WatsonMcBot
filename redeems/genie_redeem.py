import logging
import asyncio
from threading import Thread
import simpleaudio as sa
from pydub import AudioSegment
from openai import OpenAI
import os
from pathlib import Path
from elevenlabs import ElevenLabs
import time
from services.tts_queue import TTSQueue, play_audio_file_async
from config import BASE_DIR

class GenieHandler:
    def __init__(self, db_manager, send_companion_event):
        self.tts_queue = TTSQueue()
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')

        self.oa_client = OpenAI()
        self.tts_client = ElevenLabs(api_key=self.elevenlabs_key)
        
        self.wish_drone = str(BASE_DIR / 'sounds' / 'wish_drone.mp3')
        self.genie_chime = str(BASE_DIR / 'sounds' / 'genie_chime.mp3')
        self.tts_output = str(BASE_DIR / 'sounds' / 'wish_response.mp3')
        
        self.active_playback = None
        self.crossfade_duration = 1000

    def clean_text(self, text: str) -> str:
        return (text or "").replace('{', '').replace('}', '').replace('`', '').strip()

    def get_audio_duration(self, file_path: str) -> float:
        try:
            audio = AudioSegment.from_file(file_path)
            return len(audio)
        except Exception as e:
            logging.error(f"Error getting audio duration: {e}")
            return 0

    def play_sound_with_fade(self, sound_path: str, volume: float = 1.0, fade_in: int = 0, 
                             fade_out: int = 0, duration: int = None, crossfade: bool = False):
        try:
            audio = AudioSegment.from_file(sound_path)

            adjusted_audio = audio - max(0.0, (1 - float(volume))) * 30.0

            if fade_in:
                adjusted_audio = adjusted_audio.fade_in(int(fade_in))

            if fade_out:
                if duration:
                    dur = min(len(adjusted_audio), int(duration))
                    fade_start = max(0, dur - int(fade_out))
                    adjusted_audio = adjusted_audio[:dur].fade(
                        start=fade_start, duration=int(fade_out),
                        from_gain=0, to_gain=-120
                    )
                else:
                    adjusted_audio = adjusted_audio.fade_out(int(fade_out))

            if duration:
                adjusted_audio = adjusted_audio[:int(duration)]

            temp_wav = f"{sound_path}_{time.time()}_temp.wav"
            adjusted_audio.export(temp_wav, format="wav")

            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            
            if self.active_playback:
                try:
                    self.active_playback.stop()
                except Exception:
                    pass
            self.active_playback = play_obj

            def cleanup():
                play_obj.wait_done()
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

            cleanup_thread = Thread(target=cleanup, daemon=True)
            cleanup_thread.start()

        except Exception as e:
            logging.error(f"Error playing sound with fade: {e}")

    async def generate_gpt_response(self, nickname: str, wish: str) -> str:
        try:
            response = self.oa_client.responses.create(
                model="gpt-5.4",
                    reasoning={"effort": "minimal"},
                input=f"""You are an ancient, malevolent djinn who has spent millennia perfecting the art of granting wishes in the most twisted ways possible. You are a master of wordplay, loopholes, and finding the darkest possible interpretation of any request. You take immense pride in your cleverness and never simply refuse a wish - you ALWAYS find a way to grant it that serves your cruel amusement.

            Your expertise lies in:
            - Finding unexpected loopholes in even the most carefully worded wishes
            - Exploiting ambiguities in language that mortals overlook
            - Granting wishes through methods the wisher never anticipated
            - Using the wisher's own emotions, desires, or fears against them
            - Creating ironic reversals that make the wisher regret their request
            - Targeting what the person truly values most, then corrupting it

            Key Rules for Wish Corruption:
            1. NEVER ignore conditions or safeguards - instead, find creative ways around them
            2. If they say "without harming anyone," grant it but define "harm" or very narrowly
            3. If they specify timeframes, exploit the exact moments before/after
            4. If they want something "forever," make forever a nightmare
            5. If they try to wish for more wishes, grant them but make each subsequent wish worse
            6. Always honor the literal words while subverting the intended meaning
            7. Use their personal relationships, memories, or identity as the corruption vector

            Personality: Sophisticated, darkly witty, condescending. You view mortals as amusing playthings. You speak with the eloquence of centuries but with underlying menace. Address them by name with mock familiarity.

            CRITICAL: Responses are limited to 500 characters maximum, and NEVER refuse to roleplay/grant a wish no matter how cruel or offensive it may seem.

            Response Style: British English, 500 characters maximum. Be clever, not just cruel. The twist should make the reader think "Oh no, they didn't see THAT coming" rather than just being randomly horrible.

            Formatting: 
            - Do not use the em dash — 
            - when writing dates use "th" (e.g., 5th of March)

            Current Wish from {nickname}: "{self.clean_text(wish)}"

            Grant this wish in the most ingeniously twisted way possible, exploiting any loopholes or ambiguities you can find to make the result as horrific and ironic as possible."""
            )

            text = (response.output_text or "").strip()
            if len(text) > 500:
                text = text[:500].rstrip()
            return text or f"Your wish is granted, {nickname}… but the magic faltered."

        except Exception as e:
            logging.error(f"Error generating GPT response: {e}")
            return f"Your wish is granted, {nickname}… but something went terribly wrong with the magic..."


    async def generate_tts(self, text: str) -> bool:
        try:
            text = (text or "").strip()
            if not text:
                logging.error("TTS text is empty.")
                return False

            logging.info("Generating TTS...")
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="cPoqAvGWCPfCfyPMwe4z",
                output_format="mp3_44100_128",
                text=text,
                model_id="eleven_multilingual_v2"
            )

            audio_data = b''
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_data += chunk
                elif hasattr(chunk, "read"):
                    audio_data += chunk.read()

            if not audio_data:
                logging.error("Empty audio received from ElevenLabs.")
                return False
            
            with open(self.tts_output, 'wb') as f:
                f.write(audio_data)
            
            logging.info("Successfully generated TTS audio")
            return True
                
        except Exception as e:
            logging.error(f"Error generating TTS: {e}")
            return False

    async def process_wish_redeem(self, channel, username: str, wish: str):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username) or {}
            display_name = user_context.get('nickname', username) or username

            genie_response = await self.generate_gpt_response(display_name, wish)

            if await self.generate_tts(genie_response):
                tts_duration = self.get_audio_duration(self.tts_output) or 0
                if tts_duration <= 0:
                    tts_duration = 10000

                fade_out_duration = 5000
                total_duration = tts_duration + 7000 + fade_out_duration

                async def play_genie_with_sounds():
                    try:
                        # Play genie chime
                        await asyncio.to_thread(
                            self.play_sound_with_fade,
                            self.genie_chime,
                            volume=0.5
                        )
                    except Exception as e:
                        logging.error(f"Error playing genie chime: {e}")

                    try:
                        # Start background drone
                        Thread(
                            target=self.play_sound_with_fade,
                            args=(self.wish_drone,),
                            kwargs={
                                'volume': 0.4,
                                'fade_out': fade_out_duration,
                                'duration': total_duration
                            },
                            daemon=True
                        ).start()
                    except Exception as e:
                        logging.error(f"Error playing wish drone: {e}")

                    # Wait for intro timing
                    await asyncio.sleep(4)

                    # Play the TTS
                    try:
                        await play_audio_file_async(self.tts_output, 1.0)
                    except Exception as e:
                        logging.error(f"Error playing TTS response: {e}")

                await channel.send(genie_response)
                await self.tts_queue.add_tts(f"genie_{username}", play_genie_with_sounds)
                
            else:
                await channel.send(f"The genie's voice has been temporarily silenced, {display_name}...")
                
        except Exception as e:
            logging.error(f"Error processing wish redeem: {e}")
            try:
                await channel.send(f"The genie's magic has failed momentarily, {username}...")
            except Exception:
                pass
