import asyncio
import logging
from pathlib import Path
from threading import Thread
from typing import Callable, Optional
from pydub import AudioSegment
import simpleaudio as sa

class TTSQueue:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.queue = asyncio.Queue()
        self.is_playing = False
        self.current_task = None
        self._worker_task = None

    async def start_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())
            logging.info("TTS queue worker started")

    async def _process_queue(self):
        while True:
            try:
                tts_item = await self.queue.get()

                if tts_item is None:
                    break

                self.is_playing = True
                logging.info(f"Processing TTS: {tts_item['name']}")

                await tts_item['callback']()

                self.is_playing = False
                self.queue.task_done()

                await asyncio.sleep(0.5)

            except Exception as e:
                logging.error(f"Error in TTS queue worker: {e}")
                self.is_playing = False

    async def add_tts(self, name: str, callback: Callable):
        await self.queue.put({
            'name': name,
            'callback': callback
        })
        logging.info(f"Added TTS to queue: {name} (Queue size: {self.queue.qsize()})")

    def get_queue_size(self) -> int:
        return self.queue.qsize()

    def is_currently_playing(self) -> bool:
        return self.is_playing

    async def stop(self):
        await self.queue.put(None)
        if self._worker_task:
            await self._worker_task

def play_audio_file(file_path: str, volume: float = 1.0):
    try:
        audio = AudioSegment.from_file(file_path)
        adjusted_audio = audio - (1 - volume) * 30

        temp_wav = f"{file_path}_temp.wav"
        adjusted_audio.export(temp_wav, format="wav")

        wave_obj = sa.WaveObject.from_wave_file(temp_wav)
        play_obj = wave_obj.play()
        play_obj.wait_done()

        try:
            import os
            os.remove(temp_wav)
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Error playing audio: {e}")

async def play_audio_file_async(file_path: str, volume: float = 1.0):
    await asyncio.to_thread(play_audio_file, file_path, volume)
