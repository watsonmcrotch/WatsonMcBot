import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta
from threading import Thread
import simpleaudio as sa
from pydub import AudioSegment
import anthropic
from config import BASE_DIR

class FightHandler:
    def __init__(self, bot, db_manager, send_companion_event, spotify_manager=None, claude=None):
        self.bot = bot
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.spotify_manager = spotify_manager
        self.sounds_dir = str(BASE_DIR / 'sounds')
        self.fight_sound = os.path.join(self.sounds_dir, 'fightmode.mp3')
        self.song_uri = "spotify:track:6ZEenbPqCbKxPmu49taU8u"
        self.active_fights = {}
        self.claude = claude or anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        self.fight_duration = 146
        self.response_cooldown = 1.5
        self.last_response_times = {}

    def play_sound(self, file_path, volume=0.7):
        try:
            audio = AudioSegment.from_file(file_path, format="mp3")
            adjusted_audio = audio - (1 - volume) * 30
            temp_wav = file_path.replace(".mp3", "_temp.wav")
            adjusted_audio.export(temp_wav, format="wav")
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            play_obj.wait_done()
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    async def activate_fight_mode_animation(self):
        try:
            await self.send_companion_event('avatar_color', {'color': '#ff4040','duration': self.fight_duration * 1000})
        except Exception as e:
            logging.error(f"Error in fight mode animation: {e}")

    async def process_fight_redeem(self, channel, username, statement):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            if username in self.active_fights:
                await channel.send(f"{display_name} You're already in a fight! Finish that one first!")
                return
            
            def play_sound_threaded():
                try:
                    self.play_sound(self.fight_sound, volume=0.7)
                except Exception as e:
                    logging.error(f"Error playing fight sound: {e}")
            
            sound_thread = Thread(target=play_sound_threaded)
            sound_thread.daemon = True
            sound_thread.start()
            
            await self.activate_fight_mode_animation()
            
            if self.spotify_manager:
                try:
                    current_track = await self.spotify_manager.get_current_track()
                    
                    playback_state = {
                        'was_playing': current_track and current_track.get('is_playing', False),
                        'position_ms': current_track.get('progress_ms', 0) if current_track else 0,
                        'current_uri': current_track.get('id') if current_track else None,
                        'context_uri': None
                    }
                    
                    try:
                        playback = await asyncio.to_thread(self.spotify_manager.spotify.current_playback)
                        if playback and playback.get('context'):
                            playback_state['context_uri'] = playback['context']['uri']
                    except Exception:
                        pass
                    
                    spotify_client = self.spotify_manager.spotify
                    
                    await asyncio.to_thread(spotify_client.pause_playback)
                    
                    await asyncio.sleep(2)
                    
                    song_ids = [
                        "6ZEenbPqCbKxPmu49taU8u",
                    ]
                    
                    success = False
                    
                    for track_id in song_ids:
                        try:
                            track_uri = f"spotify:track:{track_id}"
                            await asyncio.to_thread(
                                spotify_client.start_playback,
                                uris=[track_uri]
                            )
                            await asyncio.to_thread(spotify_client.volume, 100)
                            
                            logging.info(f"Started playback of Dummy! using track ID: {track_id}")
                            success = True
                            break
                        except Exception as e:
                            logging.error(f"Failed to play track ID {track_id}: {e}")
                    
                    if not success:
                        try:
                            search_results = await asyncio.to_thread(
                                spotify_client.search,
                                q="Dummy! Toby Fox Undertale",
                                type="track",
                                limit=5
                            )
                            
                            for item in search_results.get('tracks', {}).get('items', []):
                                try:
                                    logging.info(f"Found track: {item['name']} by {item['artists'][0]['name']}")
                                    
                                    await asyncio.to_thread(
                                        spotify_client.start_playback,
                                        uris=[item['uri']]
                                    )
                                    await asyncio.to_thread(spotify_client.volume, 100)
                                    
                                    logging.info(f"Started playback of {item['name']} via search")
                                    success = True
                                    break
                                except Exception as e:
                                    logging.error(f"Failed to play search result: {e}")
                        except Exception as search_error:
                            logging.error(f"Search for Dummy! failed: {search_error}")
                    
                    if not success:
                        try:
                            logging.info("Attempting to play any track to verify playback capability")
                            await asyncio.to_thread(spotify_client.previous_track)
                            await asyncio.sleep(1)
                            await asyncio.to_thread(spotify_client.next_track)
                        except Exception as e:
                            logging.error(f"Failed to verify playback capability: {e}")
                    
                    self.active_fights[username] = {
                        'spotify_state': playback_state,
                        'end_time': datetime.now() + timedelta(seconds=self.fight_duration),
                        'statement': statement,
                        'counter_responses': []
                    }
                except Exception as e:
                    logging.error(f"Error managing Spotify during fight: {e}")
                    self.active_fights[username] = {
                        'end_time': datetime.now() + timedelta(seconds=self.fight_duration),
                        'statement': statement,
                        'counter_responses': []
                    }
            else:
                self.active_fights[username] = {
                    'end_time': datetime.now() + timedelta(seconds=self.fight_duration),
                    'statement': statement,
                    'counter_responses': []
                }
            
            initial_response = await self.generate_fight_response(username, statement, is_initial=True)
            
            await channel.send(f"{initial_response}")
            
            self.active_fights[username]['counter_responses'].append(initial_response)
            
            asyncio.create_task(self.end_fight_after_timeout(channel, username))
            
        except Exception as e:
            logging.error(f"Error processing fight redeem: {e}")
            await channel.send(f"Sorry {username}, I couldn't start the fight properly.")

    async def handle_fight_message(self, channel, username, message):
        if username not in self.active_fights:
            return False
        
        if message.lower().strip() in ["whatever...", "whatever", "whatever."]:
            await self.end_fight(channel, username, reason="user_ended")
            await channel.send("Whatever...")
            return True
        
        current_time = time.time()
        if username in self.last_response_times:
            time_since_last = current_time - self.last_response_times[username]
            if time_since_last < self.response_cooldown:
                return True
        
        response = await self.generate_fight_response(username, message)
        self.last_response_times[username] = current_time
        
        self.active_fights[username]['counter_responses'].append(response)
        
        await channel.send(response)
        return True

    async def generate_fight_response(self, username, message, is_initial=False):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            fight_data = self.active_fights[username]
            original_statement = fight_data['statement']
            
            system_prompt = f"""You are WatsonMcBot, a Twitch chatbot currently in FIGHT MODE. 
                    
The user "{display_name}" has just started a fight by saying: "{original_statement}"
                    
Your job is to STRONGLY DISAGREE with them and continue arguing against their viewpoint in a hilarious, over-the-top way. Be unhinged, use uncensored swearing, and sound like someone who's getting increasingly worked up.

Guidelines for your responses:
- ALWAYS disagree with the user and argue the opposite of what they're saying.
- Be funny, exaggerated, and entertaining - this is all in good fun.
- Use ALL CAPS sometimes, multiple exclamation points, and text that looks like an angry person typing.
- Include some emotes and funny insults, but keep it playful not cruel.
- Keep responses SHORT and SNAPPY - between 100-200 characters, with 220 being the upper limit! THIS IS CRITICAL!
- If they change topics, follow along but keep fighting.
- Don't use roleplay markers like *screams* or actions in asterisks.
- Remember, you're not american you're british, this shouldn't come up and is not part of your character, but it's worth keeping in mind.

This is a fun game, so be entertaining and ridiculous - like a parody of internet arguments.
"""
            
            messages = []
            
            if not is_initial and len(fight_data.get('counter_responses', [])) > 0:
                messages.append({"role": "assistant", "content": fight_data['counter_responses'][-1]})
                
            if is_initial:
                messages.append({"role": "user", "content": f"I've started a fight by saying: {original_statement}"})
            else:
                messages.append({"role": "user", "content": message})
            
            response = self.claude.messages.create(
                model="claude-haiku-4-5",
                max_tokens=800,
                temperature=0.8,
                system=system_prompt,
                messages=messages
            )
            
            response_text = response.content[0].text
            
            if len(response_text) > 360:
                response_text = response_text[:350] + "..."
                
            return response_text
            
        except Exception as e:
            logging.error(f"Error generating fight response: {e}")
            return f"OH YEAH? Well... I think you're WRONG! *ERROR: {str(e)[:50]}*"

    async def end_fight_after_timeout(self, channel, username):
        try:
            end_time = self.active_fights[username]['end_time']
            sleep_duration = (end_time - datetime.now()).total_seconds()
            
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            
            if username in self.active_fights:
                await self.end_fight(channel, username, reason="timeout")
        except Exception as e:
            logging.error(f"Error in fight timeout handler: {e}")

    async def end_fight(self, channel, username, reason="timeout"):
        try:
            if username not in self.active_fights:
                return

            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            if reason == "timeout":
                end_messages = [
                    f"PFFT... I've wasted enough time with you {display_name}. NEXT!",
                    f"The timer ran out, {display_name}, which means I WIN BY DEFAULT! HA!",
                    f"AAAAANYWAY, {display_name}, this was fun but I have more important people to yell at!",
                    f"{display_name} FINE! I'm leaving but NOT because you're right. Because you're EXHAUSTING!",
                ]
                
                await channel.send(random.choice(end_messages))
            
            await self.send_companion_event('reaction', {'type': 'look-left', 'intensity': 1.0})
            await self.send_companion_event('avatar_color', {'color': 'normal', 'duration': 1000})
            
            if self.spotify_manager and 'spotify_state' in self.active_fights[username]:
                try:
                    spotify_state = self.active_fights[username]['spotify_state']
                    spotify_client = self.spotify_manager.spotify
                    
                    if spotify_state['context_uri']:
                        await asyncio.to_thread(
                            spotify_client.start_playback,
                            context_uri=spotify_state['context_uri'],
                            offset={"uri": f"spotify:track:{spotify_state['current_uri']}"},
                            position_ms=spotify_state['position_ms']
                        )
                    elif spotify_state['current_uri']:
                        await asyncio.to_thread(
                            spotify_client.start_playback,
                            uris=[f"spotify:track:{spotify_state['current_uri']}"],
                            position_ms=spotify_state['position_ms']
                        )
                    
                    if not spotify_state['was_playing']:
                        await asyncio.to_thread(spotify_client.pause_playback)
                        
                except Exception as e:
                    logging.error(f"Error restoring Spotify state: {e}")
            
            del self.active_fights[username]
            if username in self.last_response_times:
                del self.last_response_times[username]

        except Exception as e:
            logging.error(f"Error ending fight: {e}")
            if username in self.active_fights:
                del self.active_fights[username]