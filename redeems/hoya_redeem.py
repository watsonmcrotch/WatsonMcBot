import logging
from threading import Thread
import simpleaudio as sa
from pydub import AudioSegment

class HoyaHandler:
    def __init__(self, sound_path, send_companion_event):
        self.sound_path = sound_path
        self.send_companion_event = send_companion_event

    def play_sound_threaded(self, sound_path, volume=0.6):
        audio = AudioSegment.from_mp3(sound_path)
        
        db_adjustment = 20 * (volume - 1)
        adjusted_audio = audio + db_adjustment
        
        wave_obj = sa.WaveObject(
            adjusted_audio.raw_data,
            num_channels=adjusted_audio.channels,
            bytes_per_sample=adjusted_audio.sample_width,
            sample_rate=adjusted_audio.frame_rate
        )
        play_obj = wave_obj.play()
        play_obj.wait_done()

    async def process_hoya_redeem(self, channel):
        try:
            sound_thread = Thread(
                target=self.play_sound_threaded,
                args=(self.sound_path, 0.5)
            )
            sound_thread.daemon = True
            sound_thread.start()
            
            await self.send_companion_event('reaction', {'type': 'look-up-left', 'intensity': 1.2})
        except Exception as e:
            logging.error(f"Error in hoya redeem: {e}")