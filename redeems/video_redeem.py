import asyncio
import logging
from pathlib import Path
from threading import Thread
from pydub import AudioSegment
import simpleaudio as sa
from datetime import datetime
import discord
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from google import genai
from google.genai import types
from config import BASE_DIR

load_dotenv()

class SoundPlaybackManager:
    def __init__(self):
        self.active_playback = None
        self.executor = ThreadPoolExecutor(max_workers=2)

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


class VideoRedeemHandler:
    def __init__(self, db_manager, discord_monitor, send_companion_event=None):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.discord_monitor = discord_monitor
        self.playback_manager = SoundPlaybackManager()
        
        self.base_dir = BASE_DIR
        self.assets_dir = self.base_dir / 'overlays' / 'assets'
        self.videos_dir = self.assets_dir / 'videos'
        self.sounds_dir = self.base_dir / 'sounds'
        
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        self.init_sound = str(self.sounds_dir / 'video_init.mp3')
        self.start_sound = str(self.sounds_dir / 'video_start.mp3')
        self.complete_sound = str(self.sounds_dir / 'video_finished.mp3')
        self.fail_sound = str(self.sounds_dir / 'video_fail.mp3')
        
        if not Path(self.init_sound).exists():
            self.init_sound = str(self.sounds_dir / 'video_init.wav')
        if not Path(self.start_sound).exists():
            self.start_sound = str(self.sounds_dir / 'video_start.wav')
        if not Path(self.complete_sound).exists():
            self.complete_sound = str(self.sounds_dir / 'video_finished.wav')
        if not Path(self.fail_sound).exists():
            self.fail_sound = str(self.sounds_dir / 'video_fail.wav')
        
        self.genai_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

        self.discord_channel_id = int(os.getenv('DISCORD_CHANNEL_VIDEOS')) if os.getenv('DISCORD_CHANNEL_VIDEOS') else None
        
        self.last_video_data = {}
        self.pending_videos = {}
        self.awaiting_retry = {}
        self.retry_timeout = 300
        self.replay_in_progress = False
        self.replay_queue = []
        self.replay_lock = asyncio.Lock()

    def is_replay_available(self):
        # Simply check if there's a last video with required data
        return bool(self.last_video_data and
                   'web_video_path' in self.last_video_data and
                   'username' in self.last_video_data)

    async def handle_chat_message(self, channel, username: str, message: str):
        if username not in self.awaiting_retry:
            return False

        retry_data = self.awaiting_retry[username]

        time_elapsed = (datetime.now() - retry_data['timestamp']).total_seconds()
        if time_elapsed > self.retry_timeout:
            del self.awaiting_retry[username]
            await channel.send(f"@{username}, your retry window has expired. Please redeem again if you want to try.")
            return True

        if not message.strip().lower().startswith('retry'):
            return False

        new_prompt = message.strip()[5:].strip()

        if not new_prompt:
            await channel.send(f"@{username}, include a prompt after 'retry'. Example: retry a cat playing piano")
            return False

        user_color = retry_data.get('user_color')

        del self.awaiting_retry[username]

        await self.process_video_redeem(
            channel=channel,
            username=username,
            prompt=new_prompt,
            user_color=user_color,
            is_retry=True
        )

        return True

    async def process_video_redeem(self, channel, username: str, prompt: str, user_color=None, is_retry=False):
        user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
        display_name = user_context.get('nickname', username)
        
        if not prompt or not prompt.strip():
            await channel.send(f"Sorry {display_name}, you need to provide a prompt for the video!")
            return False
        
        prompt = prompt.strip()
        
        logging.info(f"Processing video redeem for {display_name} with prompt: {prompt}")
        
        try:
            self.playback_manager.play_sound(self.start_sound, volume=1.0)
        except Exception as e:
            logging.error(f"Error playing start sound: {e}")
        
        await channel.send(f"Generating video for {display_name}! This will take a moment...")
        
        try:
            video_url = await self.generate_video(prompt, username, channel, display_name)
            
            video_path, web_video_path = await self.download_video(video_url)
            
            try:
                self.playback_manager.play_sound(self.complete_sound, volume=1.0)
            except Exception as e:
                logging.error(f"Error playing complete sound: {e}")
            
            await channel.send(f"@{username} your video is ready!")
            
            await asyncio.sleep(3)
            
            try:
                if not user_color:
                    user_color = (await asyncio.to_thread(self.db_manager.get_user_context, username)).get('color', '#FF69B4')
                
                video_duration = 16000
                
                await asyncio.gather(
                    self.send_companion_event('show-video', {
                        'url': web_video_path,
                        'style': {
                            'position': 'absolute',
                            'top': '40px',
                            'left': '40px',
                            'width': '800px',
                            'height': '450px',
                            'borderRadius': '14px',
                            'shadow': '4px 4px 10px rgba(0,0,0,0.5)',
                            'margin': '0, 0, 20px, 0',
                        },
                        'animateIn': 'fadeIn',
                        'animateOut': 'fadeOut',
                        'duration': video_duration,
                        'volume': 0.5,
                        'autoplay': True
                    }),
                    self.send_companion_event('text-overlay', {
                        'content': display_name,
                        'style': {
                            'position': 'absolute',
                            'top': '505px',
                            'left': '40px',
                            'fontSize': '24px',
                            'fontWeight': 'bold',
                            'color': user_color,
                            'textShadow': '2px 2px 4px rgba(0,0,0,0.8)',
                            'fontFamily': 'Montserrat, Arial, sans-serif',
                            'zIndex': '1000'
                        },
                        'animateIn': 'fadeIn',
                        'animateOut': 'fadeOut',
                        'duration': video_duration
                    })
                )
                
                # Update last video data - this replaces any previous video
                self.last_video_data = {
                    'username': username,
                    'video_path': video_path,
                    'web_video_path': web_video_path,
                    'user_color': user_color,
                    'display_name': display_name,
                    'prompt': prompt,
                    'timestamp': datetime.now()
                }
                    
            except Exception as e:
                logging.error(f"Error sending overlay event: {e}")
                    
            try:
                await self.share_to_discord(display_name, prompt, video_path, channel_id=self.discord_channel_id)
            except Exception as e:
                logging.error(f"Error sharing to Discord: {e}")
            
            if username in self.pending_videos:
                del self.pending_videos[username]
                    
            return True
                
        except Exception as e:
            error_message = str(e)
            logging.error(f"Error processing video redeem: {error_message}")

            if username in self.pending_videos:
                del self.pending_videos[username]

            # Parse error code and message if available
            error_code = "unknown"
            error_detail = error_message
            if "||" in error_message:
                error_code, error_detail = error_message.split("||", 1)

            # Determine if this is a retryable error
            is_moderation_error = 'moderation' in error_code.lower() or 'content_policy' in error_code.lower() or 'safety' in error_code.lower()
            is_moderation_error = is_moderation_error or 'moderation' in error_detail.lower() or 'content policy' in error_detail.lower() or 'safety' in error_detail.lower()

            try:
                self.playback_manager.play_sound(self.fail_sound, volume=1.0)
            except Exception as sound_e:
                logging.error(f"Error playing fail sound: {sound_e}")

            if is_moderation_error:
                self.awaiting_retry[username] = {
                    'timestamp': datetime.now(),
                    'user_color': user_color,
                    'channel': channel,
                    'error_code': error_code,
                    'error_detail': error_detail
                }

                await channel.send(f"Hey @{display_name}, that prompt got flagged. Reason: {error_detail}. You can skip the cooldown and try again by typing 'retry' followed by a new prompt within 5 minutes.")
                return 'moderation_failure'
            else:
                # Non-retryable error - provide specific feedback
                error_responses = {
                    "invalid_prompt": f"@{display_name}, the AI couldn't understand that prompt. Error: {error_detail}. Please redeem again with a clearer description.",
                    "rate_limit": f"@{display_name}, we're being rate limited. Error: {error_detail}. Please try again in a minute.",
                    "timeout": f"@{display_name}, the video generation timed out. Error: {error_detail}. Please try again.",
                    "network_error": f"@{display_name}, there was a network issue. Error: {error_detail}. Please try again.",
                }

                # Get error message, with fallback
                error_msg = error_responses.get(error_code)
                if not error_msg:
                    # Check if error code starts with known prefixes
                    if error_code.startswith("http_"):
                        error_msg = f"@{display_name}, the API returned an error. Error: {error_detail}. Please try again later."
                    else:
                        error_msg = f"Sorry @{display_name}, video generation failed. Error: {error_detail}. Please try again later."

                await channel.send(error_msg)

            return False

    async def generate_video(self, prompt: str, username: str, channel, display_name: str) -> str:
        try:
            logging.info(f"Starting Veo 3.1 video generation with prompt: {prompt}")

            self.pending_videos[username] = {
                'prompt': prompt,
                'start_time': datetime.now()
            }

            # Start generation (sync SDK call in thread)
            operation = await asyncio.to_thread(
                self.genai_client.models.generate_videos,
                model="veo-3.1-generate-preview",
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    person_generation="allow_all",
                ),
            )

            logging.info(f"Veo 3.1 generation started: {operation.name}")

            # Poll until done
            poll_count = 0
            max_polls = 60  # ~10 min at 10s intervals
            consecutive_failures = 0
            max_consecutive_failures = 5

            while not operation.done:
                await asyncio.sleep(10)
                poll_count += 1

                if poll_count > max_polls:
                    raise Exception("timeout||Video generation timed out after polling limit")

                try:
                    operation = await asyncio.to_thread(
                        self.genai_client.operations.get, operation
                    )
                    consecutive_failures = 0
                except Exception as poll_err:
                    consecutive_failures += 1
                    logging.warning(f"Poll error (attempt {poll_count}, consecutive failures: {consecutive_failures}): {poll_err}")
                    if consecutive_failures >= max_consecutive_failures:
                        raise Exception(f"network_error||Too many consecutive poll failures: {poll_err}")
                    continue

                if poll_count % 6 == 0:
                    logging.info(f"Veo status check #{poll_count}: done={operation.done}")

                # Send periodic chat updates every ~30s
                if channel and display_name and poll_count % 3 == 0:
                    try:
                        await channel.send(f"{display_name}'s video is still generating...")
                    except Exception as e:
                        logging.error(f"Error sending progress update to chat: {e}")

            logging.info("Veo 3.1 video generation completed successfully")

            # Download and save the video
            generated_video = operation.response.generated_videos[0]
            await asyncio.to_thread(
                self.genai_client.files.download, file=generated_video.video
            )

            unique_id = f"{int(datetime.now().timestamp())}_{os.urandom(2).hex()}"
            video_filename = f'video_output_{unique_id}.mp4'
            video_path = self.videos_dir / video_filename

            await asyncio.to_thread(generated_video.video.save, str(video_path))

            web_path = f'http://localhost:5555/assets/videos/{video_filename}'

            if username in self.pending_videos:
                del self.pending_videos[username]

            return web_path

        except Exception as e:
            error_str = str(e)
            logging.error(f"Error in generate_video: {error_str}")

            # Map common Veo/Gemini errors to the existing error||message format
            error_lower = error_str.lower()
            if any(kw in error_lower for kw in ['safety', 'blocked', 'content policy', 'moderation', 'prohibited']):
                if '||' not in error_str:
                    raise Exception(f"content_policy||{error_str}")
            elif 'rate' in error_lower and 'limit' in error_lower:
                if '||' not in error_str:
                    raise Exception(f"rate_limit||{error_str}")

            raise
    
    async def download_video(self, video_url: str):
        try:
            if video_url.startswith('http://localhost:5555'):
                logging.info(f"Video already saved locally: {video_url}")
                
                video_filename = video_url.split('/')[-1]
                video_path = self.videos_dir / video_filename
                web_path = video_url
                
                return video_path, web_path
            
            logging.error(f"Unexpected video URL format: {video_url}")
            raise Exception(f"Unexpected video URL format: {video_url}")
            
        except Exception as e:
            logging.error(f"Error in download_video: {e}")
            raise
    
    async def handle_replay_command(self, channel, username: str, broadcaster_name: str):
        if not self.is_replay_available():
            await channel.send("No video available to replay!")
            return False

        original_user = self.last_video_data.get('username')

        # Only allow the original user or the broadcaster to replay
        if username.lower() != original_user.lower() and username.lower() != broadcaster_name.lower():
            await channel.send(f"Sorry @{username}, only @{original_user} or the broadcaster can replay this video!")
            return False

        async with self.replay_lock:
            if self.replay_in_progress:
                queue_position = len(self.replay_queue) + 1
                if queue_position > 3:
                    await channel.send(f"@{username} replay queue is full! Please wait for current replays to finish.")
                    return False

                self.replay_queue.append((channel, username))
                await channel.send(f"@{username} added to replay queue (position {queue_position})")
                return True

            self.replay_in_progress = True

        try:
            await self._execute_replay(channel, username, original_user)

            while self.replay_queue:
                replay_channel, replay_username = self.replay_queue.pop(0)

                await asyncio.sleep(1)

                if not self.is_replay_available():
                    await replay_channel.send(f"@{replay_username} no video available to replay.")
                    continue

                await self._execute_replay(replay_channel, replay_username, original_user)

            return True

        except Exception as e:
            logging.error(f"Error in replay command: {e}")
            await channel.send("Failed to replay video!")
            return False
        finally:
            async with self.replay_lock:
                self.replay_in_progress = False
    
    async def _execute_replay(self, channel, username: str, original_user: str):
        try:
            video_duration = 16000

            await asyncio.gather(
                self.send_companion_event('show-video', {
                    'url': self.last_video_data['web_video_path'],
                    'style': {
                        'position': 'absolute',
                        'top': '40px',
                        'left': '40px',
                        'width': '800px',
                        'height': '450px',
                        'borderRadius': '14px',
                        'shadow': '4px 4px 10px rgba(0,0,0,0.5)',
                        'margin': '0, 0, 20px, 0',
                    },
                    'animateIn': 'fadeIn',
                    'animateOut': 'fadeOut',
                    'duration': video_duration,
                    'volume': 0.5,
                    'autoplay': True
                }),
                self.send_companion_event('text-overlay', {
                    'content': self.last_video_data['display_name'],
                    'style': {
                        'position': 'absolute',
                        'top': '505px',
                        'left': '40px',
                        'fontSize': '24px',
                        'fontWeight': 'bold',
                        'color': self.last_video_data['user_color'],
                        'textShadow': '2px 2px 4px rgba(0,0,0,0.8)',
                        'fontFamily': 'Montserrat, Arial, sans-serif',
                        'zIndex': '1000'
                    },
                    'animateIn': 'fadeIn',
                    'animateOut': 'fadeOut',
                    'duration': video_duration
                })
            )

            await channel.send(f"Replaying video for @{original_user}!")

        except Exception as e:
            logging.error(f"Error executing replay: {e}")
            raise
    
    async def share_to_discord(self, username: str, prompt: str, video_path: Path, channel_id: int = None):
        try:
            if channel_id is None:
                channel_id = self.discord_channel_id
            
            if channel_id is None or channel_id == 0:
                target_channel_id = None
            else:
                target_channel_id = channel_id if channel_id != 0 else 1297522580944719935
            
            if target_channel_id is None:
                user = await self.discord_monitor.fetch_user(self.discord_monitor.discord_user_id)
                if user:
                    with open(video_path, 'rb') as file:
                        discord_file = discord.File(file, filename='video_output.mp4')
                        await user.send(content=f"**{username}**: *\"{prompt}\"*", file=discord_file)
                else:
                    logging.error(f"Could not find Discord user with ID {self.discord_monitor.discord_user_id}")
            else:
                channel = self.discord_monitor.get_channel(target_channel_id)
                if channel:
                    with open(video_path, 'rb') as file:
                        discord_file = discord.File(file, filename='video_output.mp4')
                        await channel.send(content=f"**{username}**: *\"{prompt}\"*", file=discord_file)
                        
                        if hasattr(self.discord_monitor, 'creative_redeems'):
                            self.discord_monitor.creative_redeems.update_generation('video', {
                                'prompt': prompt,
                                'user': username,
                                'timestamp': datetime.now().isoformat()
                            })
                else:
                    logging.error(f"Could not find Discord channel with ID {target_channel_id}")
        except Exception as e:
            logging.error(f"Error sharing to Discord: {e}")
            raise