import logging
from pydub import AudioSegment
import simpleaudio as sa
from threading import Thread
import asyncio
import re

class NicknameHandler:
    def __init__(self, db_manager, sound_path: str, send_companion_event=None):
        self.db_manager = db_manager
        self.sound_path = sound_path
        self.send_companion_event = send_companion_event

    def play_sound_threaded(self, sound_path: str, volume: float = 0.5):
        try:
            audio = AudioSegment.from_file(sound_path)
            adjusted_audio = audio - (1 - volume) * 30
            temp_wav = sound_path.replace(".mp3", "_temp.wav")
            adjusted_audio.export(temp_wav, format="wav")
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            play_obj.wait_done()
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    def is_safe_nickname(self, nickname: str) -> bool:
        dangerous_patterns = [
            r'[<>{}()\[\]\\"\\]',
            r'(?i)javascript:',
            r'(?i)data:',
            r'(?i)script',
            r'(?i)alert\s*\(',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, nickname):
                return False
        return True

    async def process_nickname_change(self, channel, username: str, new_nickname: str) -> None:
        try:
            try:
                sound_thread = Thread(target=self.play_sound_threaded, 
                    args=(self.sound_path, 0.5))
                sound_thread.daemon = True
                sound_thread.start()
            except Exception as e:
                logging.error(f"Error playing nickname sound: {e}")

            if not new_nickname:
                await channel.send(f"Umm {username}, it helps if you actually tell me what nickname you want...")
                return

            if len(new_nickname) > 30:
                await channel.send(f"Sorry {username}, that's a bit too long. Keep it under 30 characters.")
                return

            if not self.is_safe_nickname(new_nickname):
                await channel.send(f"Sorry {username}, that nickname contains weird characters.")
                return

            try:
                user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
                current_nickname = user_context.get('nickname', username)

                await asyncio.to_thread(self.db_manager.add_nickname, username, new_nickname)
                await channel.send(f"Updated! I'll now call you '{new_nickname}' instead of '{current_nickname}'!")

                if self.send_companion_event:
                    await self.send_companion_event('reaction', {'type': 'success', 'intensity': 1.0})

                logging.info(f"Updated nickname for {username} to {new_nickname}")
            except Exception as e:
                logging.error(f"Database error updating nickname for {username}: {e}")
                await channel.send(f"Sorry {username}, something went wrong saving your nickname. Try again in a bit!")

            if self.send_companion_event:
                await self.send_companion_event('reaction', {'type': 'success', 'intensity': 1.0})
                
        except Exception as e:
            logging.error(f"Error processing nickname change: {e}")
            await channel.send(f"Sorry {username}, something went wrong with the nickname change!")