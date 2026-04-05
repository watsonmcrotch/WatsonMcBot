import aiohttp
import asyncio
import logging
import os
from pathlib import Path
import simpleaudio as sa
from datetime import datetime
import discord
import json
import re
import requests
from pydub import AudioSegment
import time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from config import BASE_DIR

class SongPlaybackManager:
    def __init__(self):
        self.active_playback = None

    def play_sound(self, sound_path: str, volume: float = 1.0, fade_in: int = 0, fade_out: int = 0):
        try:
            if self.active_playback:
                self.active_playback.stop()
                self.active_playback = None

            audio = AudioSegment.from_file(sound_path)
            adjusted_audio = audio - (1 - volume) * 30

            if fade_in:
                adjusted_audio = adjusted_audio.fade_in(fade_in)
            if fade_out:
                adjusted_audio = adjusted_audio.fade_out(fade_out)

            temp_wav = f"{sound_path}_{time.time()}_temp.wav"
            adjusted_audio.export(temp_wav, format="wav")

            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
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
            logging.error(f"Error playing sound: {e}")

class SongRedeemHandler:
    def __init__(self, db_manager, discord_monitor, send_companion_event=None, spotify_manager=None):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.discord_monitor = discord_monitor
        self.spotify_manager = spotify_manager
        self.playback_manager = SongPlaybackManager()

        self.api_url = "https://api.acedata.cloud/suno/audios"
        self.auth_token = os.getenv('ACE_AUTH_TOKEN')
        self.app_id = os.getenv('ACE_APP_ID')

        self.base_dir = BASE_DIR
        self.assets_dir = self.base_dir / 'overlays' / 'assets'
        self.images_dir = self.assets_dir / 'images'
        self.sounds_dir = self.base_dir / 'sounds'

        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        
        self.start_sound = str(self.sounds_dir / 'song_start.wav')
        self.complete_sound = str(self.sounds_dir / 'song_complete.wav')
        self.discord_channel_id = int(os.getenv('DISCORD_CHANNEL_MUSIC'))
        
        self.custom_song_users = {}
        self.max_lyric_messages = 6
        self.creation_timeout = 300
        self.timeout_tasks = {}

    def clean_user_message(self, message: str) -> str:
        message = re.sub(r'@watsonmcbot\s*', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^!?\s*', '', message)
        return message.strip()

    def is_done_message(self, message: str) -> bool:
        cleaned = message.lower().strip(' .,!?')
        return cleaned in ['done', 'dnoe', 'don', 'dune', 'dine', 'dn', 'finish', 'finished', 'end']
    
    def process_lyrics(self, lyrics: str) -> str:
        lyrics = re.sub(r'(Mr\.|Mrs\.|Dr\.|Ms\.|vs\.|etc\.)', lambda m: m.group().replace('.', '@@@'), lyrics)
        lyrics = re.sub(r'\[(verse|chorus|bridge|outro|intro)(?:\s*\d*)?\]', r'\n\n[\1]', lyrics, flags=re.IGNORECASE)
        lines = [line.strip() for line in lyrics.split('.') if line.strip()]
        processed_lyrics = '\n'.join(lines)
        processed_lyrics = processed_lyrics.replace('@@@', '.')
        processed_lyrics = re.sub(r'\n{3,}', '\n\n', processed_lyrics)
        processed_lyrics = '\n'.join(line for line in processed_lyrics.split('\n') if line.strip())
        return processed_lyrics

    async def start_timeout_task(self, username: str):
        if username in self.timeout_tasks:
            self.timeout_tasks[username].cancel()
        
        async def timeout_handler():
            await asyncio.sleep(self.creation_timeout)
            if username in self.custom_song_users:
                del self.custom_song_users[username]
                channel = self.discord_monitor.get_channel(os.getenv('CHANNEL_USERNAME'))
                if channel:
                    await channel.send(f"Sorry {username}, your custom song creation has timed out! Please try again later.")

        self.timeout_tasks[username] = asyncio.create_task(timeout_handler())

    async def handle_chat_message(self, channel, username: str, message: str):
        if username not in self.custom_song_users:
            return False

        await self.start_timeout_task(username)
        user_state = self.custom_song_users[username]
        cleaned_message = self.clean_user_message(message)

        if user_state['state'] == 'awaiting_topic':
            user_state['prompt'] = cleaned_message
            user_state['state'] = 'awaiting_style'
            await channel.send(f"Got it! Next tell me the style / genre of your song!")
            return True

        elif user_state['state'] == 'awaiting_style':
            user_state['style'] = cleaned_message
            user_state['state'] = 'awaiting_lyrics'
            await channel.send("Okay great! Now give me your lyrics! You can use up to 6 messages in chat. Don't forget to use full stops to separate lines and tags like [verse1] [verse 2] [chorus] [bridge] [outro] etc. to help the A.I understand what you want. When you're finished just type \"Done\" in chat!")
            return True

        elif user_state['state'] == 'awaiting_lyrics':
            if self.is_done_message(cleaned_message):
                if not user_state['lyrics']:
                    await channel.send(f"Hey {username}, you haven't given me any lyrics yet! Please send some lyrics first.")
                    return True
                
                user_state['state'] = 'awaiting_title'
                await channel.send(f"Okay fantastic, I've got all your lyrics! Finally, can you give me a title for your new masterpiece?")
                return True

            if not hasattr(user_state, 'message_count'):
                user_state['message_count'] = 0
            
            if user_state['message_count'] >= self.max_lyric_messages:
                await channel.send(f"Sorry {username}, you've reached the maximum number of messages (6). Please type 'done' to continue.")
                return True

            if len(user_state['lyrics']) > 0:
                user_state['lyrics'] += ' ' + cleaned_message
            else:
                user_state['lyrics'] = cleaned_message
                
            user_state['message_count'] = user_state.get('message_count', 0) + 1
            return True

        elif user_state['state'] == 'awaiting_title':
            user_state['state'] = 'processing'
            user_state['title'] = cleaned_message
            await self.finalize_custom_song(channel, username)
            return True
        
        elif user_state['state'] == 'processing':
            return True

        return False
    
    async def start_custom_song_creation(self, channel, username: str):
        user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
        display_name = user_context.get('nickname', username)
        
        self.custom_song_users[username] = {
            'state': 'awaiting_topic',
            'prompt': '',
            'style': '',
            'lyrics': '',
            'title': ''
        }
        
        await self.start_timeout_task(username)
        await channel.send(f"Hey {display_name}, let's make your custom song! First can you tell me what is the song about?")

    async def finalize_custom_song(self, channel, username: str):
        try:
            user_state = self.custom_song_users[username]
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            processed_lyrics = self.process_lyrics(user_state['lyrics'])
            
            await channel.send(f"Alright {display_name}, I'm going to create your custom song '{user_state['title']}' now! This might take a minute...")

            await self._generate_and_play_song(
                channel=channel,
                username=username,
                prompt=user_state['prompt'],
                custom_lyrics=processed_lyrics,
                custom_title=user_state['title']
            )

        except Exception as e:
            logging.error(f"Error finalizing custom song: {e}")
            await channel.send(f"Sorry {username}, something went wrong while creating your custom song!")
        finally:
            if username in self.custom_song_users:
                del self.custom_song_users[username]
            if username in self.timeout_tasks:
                self.timeout_tasks[username].cancel()
                del self.timeout_tasks[username]

    async def generate_song(self, prompt: str, custom_lyrics: str = None) -> dict:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.auth_token}",
                "x-application-id": self.app_id
            }
            
            payload = {
                "action": "generate",
                "prompt": prompt,
                "model": "chirp-v5-5",
                "instrumental": False,
                "custom": bool(custom_lyrics)
            }

            if custom_lyrics:
                user_state = next((state for username, state in self.custom_song_users.items()), None)
                if user_state:
                    payload["prompt"] = user_state['prompt']
                    payload["style"] = user_state['style']
                    payload["lyric"] = custom_lyrics
                    payload["title"] = user_state['title']

            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"API request failed with status {response.status}")
                
                data = await response.json()
                
                if not data.get("success") or "data" not in data or not data["data"]:
                    raise Exception("No song data returned from API")
                
                return data["data"][0]

    async def process_song_redeem(self, channel, username: str, prompt: str, user_color: str = "#FF69B4"):
        cleaned_prompt = prompt.lower().strip(' .,!?')
        if cleaned_prompt in ['custom', 'costum', 'custem', 'custum']:
            await self.start_custom_song_creation(channel, username)
        else:
            try:
                asyncio.create_task(self._generate_and_play_song(channel, username, prompt))
            except Exception as e:
                logging.error(f"Error initiating song redeem: {e}")
                await channel.send(f"Sorry {username}, something went wrong!")

    async def _generate_and_play_song(self, channel, username: str, prompt: str, custom_lyrics: str = None, custom_title: str = None, user_color: str = "#FF69B4"):
        spotify_was_playing = False
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            self.playback_manager.play_sound(self.start_sound, volume=0.6)

            if self.send_companion_event:
                await self.send_companion_event('reaction', {'type': 'music', 'intensity': 1.0})

            song_data = await self.generate_song(prompt, custom_lyrics)
            
            song_path = self.sounds_dir / 'generated_song.mp3'
            art_path = self.images_dir / 'album_art.png'

            await asyncio.gather(
                self.download_file(song_data['audio_url'], song_path),
                self.download_file(song_data['image_url'], art_path)
            )
            
            song_title = custom_title if custom_title else song_data.get('title', 'Untitled')

            self.playback_manager.play_sound(self.complete_sound, volume=0.6)
            await channel.send(f"@{display_name} Your song '{song_title}' is ready! 🎵")
            
            await self.share_to_discord(display_name, prompt, str(song_path), str(art_path), song_title)

            if self.spotify_manager:
                try:
                    current_playback = await self.spotify_manager.get_current_track()
                    if current_playback and current_playback.get('is_playing', False):
                        spotify_was_playing = True
                        await asyncio.to_thread(self.spotify_manager.spotify.pause_playback)
                except Exception as e:
                    logging.error(f"Error handling Spotify: {e}")

            audio = AudioSegment.from_mp3(song_path)
            duration_ms = len(audio)
            display_duration = duration_ms - 2000

            if self.send_companion_event:
                try:
                    await asyncio.gather(
                        self.send_companion_event('show-image', {
                            'url': '/assets/images/album_art.png',
                            'style': {
                                'position': 'absolute',
                                'top': '40px',
                                'left': '40px',
                                'width': '360px',
                                'height': '360px',
                                'borderRadius': '10px',
                                'Shadow': '2px 2px 4px rgba(0,0,0,0.5)',
                                'margin': '0, 0, 20px, 0',
                            },
                            'animateIn': 'fadeIn',
                            'animateOut': 'fadeOut',
                            'duration': display_duration,
                        }),
                        self.send_companion_event('text-overlay', {
                            'content': f'{display_name}',
                            'style': {
                                'fontFamily': 'Montserrat',
                                'fontWeight': '800',
                                'fontSize': '40px',
                                'textAlign': 'left',
                                'color': user_color,
                                'position': 'absolute',
                                'text-shadow': '1px 2px 2px rgba(0,0,0, 0.5',
                                'margin': '0, 0, 20px, 0',
                            },
                            'position': {
                                'top': '405px',
                                'left': '40px'
                            },
                            'animateIn': 'fadeIn',
                            'animateOut': 'fadeOut',
                            'duration': display_duration,
                        }),
                        self.send_companion_event('text-overlay', {
                            'content': f'{song_title}',
                            'style': {
                                'fontFamily': 'Montserrat',
                                'fontWeight': '700',
                                'fontSize': '32px',
                                'textAlign': 'left',
                                'color': 'white',
                                'position': 'absolute',
                                'maxWidth': '640px',
                                'text-shadow': '1px 2px 2px rgba(0,0,0, 0.5',
                            },
                            'position': {
                                'top': '460px',
                                'left': '40px'
                            },
                            'animateIn': 'fadeIn',
                            'animateOut': 'fadeOut',
                            'duration': display_duration,
                        })
                    )
                except Exception as e:
                    logging.error(f"Error sending overlay events: {e}")

            self.playback_manager.play_sound(str(song_path), volume=0.6, fade_in=1000, fade_out=1000)
            await asyncio.sleep(duration_ms / 1000)

        except Exception as e:
            logging.error(f"Error processing song redeem: {e}")
            await channel.send(f"Sorry {username}, something went wrong!")

        finally:
            if spotify_was_playing and self.spotify_manager:
                try:
                    await asyncio.to_thread(self.spotify_manager.spotify.start_playback)
                except Exception as e:
                    logging.error(f"Error resuming Spotify: {e}")

    async def download_file(self, url: str, filepath: Path):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download file. Status: {response.status}")
                
                with open(filepath, 'wb') as f:
                    f.write(await response.read())

    async def share_to_discord(self, username: str, prompt: str, song_path: str, art_path: str, title: str):
        try:
            if any(state.get('title') == title for state in self.custom_song_users.values()):
                user_state = next((state for state in self.custom_song_users.values() if state.get('title') == title), None)
                message = f"**{username}** - *\"{title}\"*\nTopic: *\"{user_state['prompt']}\"*\nStyle: *\"{user_state['style']}\"*"
            else:
                message = f"**{username}** - *\"{title}\"*\nPrompt: *\"{prompt}\"*"

            if self.discord_channel_id is None:
                user = await self.discord_monitor.fetch_user(self.discord_monitor.discord_user_id)
                if user:
                    files = [discord.File(song_path), discord.File(art_path)]
                    await user.send(content=message, files=files)
                else:
                    logging.error(f"Could not find Discord user with ID {self.discord_monitor.discord_user_id}")
            else:
                channel = self.discord_monitor.get_channel(self.discord_channel_id)
                if channel:
                    files = [discord.File(song_path), discord.File(art_path)]
                    await channel.send(content=message, files=files)
                    
                    self.discord_monitor.creative_redeems.update_generation('song', {
                        'prompt': prompt,
                        'user': username,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    logging.error(f"Could not find Discord channel with ID {self.discord_channel_id}")
        except Exception as e:
            logging.error(f"Error sharing to Discord: {e}")