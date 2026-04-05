import logging
import asyncio
import random
import aiohttp
import anthropic
import os
import html
from datetime import datetime, timedelta
from threading import Thread
from pathlib import Path
from pydub import AudioSegment
from models import TriviaGame, TriviaRound, TriviaStats
from services.websocket_server import WEB_SERVER_URL
import simpleaudio as sa
import json
from typing import Dict, List, Optional
from elevenlabs import ElevenLabs
from services.tts_queue import TTSQueue, play_audio_file_async
from config import BASE_DIR

class TriviaGameShow:
    def __init__(self, db_manager, send_companion_event, claude=None):

        self.tts_queue = TTSQueue()
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
        self.setup_pending_users = set()
        self.setup_timeout = 60
        self.setup_timeout_tasks = {}
        self.open_setup = False

        self.base_dir = BASE_DIR

        self.claude = claude or anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        self.tts_client = ElevenLabs(api_key=self.elevenlabs_key)
        
        self.sound_durations = {
            'intro': 10.0,
            'outro': 10.0,
            'thinking': 30.0,
            'countdown': 5,
            '10seconds': 2.0,
            'timesup': 1.5
        }
        
        self.audio_queue = asyncio.Queue()
        self.audio_task = None
        self.current_audio = None
        
        self.tts_output = str(self.base_dir / 'sounds' / 'host_voice.mp3')
        
        self.sound_files = {
            'intro': str(self.base_dir / 'sounds' / 'intro.mp3'),
            'outro': str(self.base_dir / 'sounds' / 'outro.mp3'),
            'thinking': str(self.base_dir / 'sounds' / 'thinking.mp3'),
            'countdown': str(self.base_dir / 'sounds' / 'countdown.mp3'),
            '10seconds': str(self.base_dir / 'sounds' / '10seconds.mp3'),
            'timesup': str(self.base_dir / 'sounds' / 'timesup.mp3')
        }
        
        self.active_games = {}
        self.current_question = None
        self.answer_window = 30
        self.min_players = 2
        self.custom_categories = ['community']
        self.categories = {
            'general': 9,
            'books': 10,
            'film': 11,
            'music': 12,
            'tv': 14,
            'gaming': 15,
            'science': 17,
            'computers': 18,
            'math': 19,
            'sports': 21,
            'geography': 22,
            'history': 23,
            'politics': 24,
            'art': 25,
            'celebrities': 26,
            'animals': 27,
            'community': 'community',
            'random': None
        }

    async def calculate_element_positions(self, question_text: str) -> dict:
        chars_per_line = 50
        num_lines = max(1, len(question_text) // chars_per_line)
        question_height = 130 + (num_lines - 1) * 40
        
        return {
            'question_top': 130,
            'answers_base_top': question_height + 50,
            'timer_top': question_height + 300,
            'stats_top': question_height + 350
        }

    async def queue_audio(self, audio_type: str, data: dict) -> asyncio.Task:
        item = {
            'type': audio_type,
            'data': data,
            'timestamp': datetime.now()
        }
        await self.audio_queue.put(item)
        
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self.process_audio_queue())
        
        return self.audio_task

    async def process_audio_queue(self):
        while True:
            if self.audio_queue.empty():
                break
                
            try:
                audio_item = await self.audio_queue.get()
                audio_type = audio_item['type']
                data = audio_item['data']
                
                if audio_type == 'sound':
                    await self.play_sound_and_wait(data['name'], data['volume'])
                elif audio_type == 'tts':
                    await self._generate_and_play_host_voice(data['text'])
                elif audio_type == 'background':
                    await self.play_background_music(data['name'], data['volume'])
                    
                self.audio_queue.task_done()
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logging.error(f"Error processing audio queue: {e}")
                self.audio_queue.task_done()

    async def play_background_music(self, sound_name: str, volume: float = 0.3):
        try:
            if self.current_audio:
                self.current_audio.stop()
            
            audio = AudioSegment.from_file(self.sound_files[sound_name])
            temp_wav = f"{self.sound_files[sound_name]}_bg_temp.wav"
            audio.export(temp_wav, format="wav")
            
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
        except Exception as e:
            logging.error(f"Error playing background music: {e}")

    async def play_sound_and_wait(self, sound_name: str, volume: float = 0.6):
        if sound_name not in self.sound_files:
            return
                
        try:
            if self.current_audio:
                self.current_audio.stop()
                
            audio = AudioSegment.from_file(self.sound_files[sound_name])
            temp_wav = f"{self.sound_files[sound_name]}_temp.wav"
            audio.export(temp_wav, format="wav")
            
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            await asyncio.sleep(self.sound_durations[sound_name])
            
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
        except Exception as e:
            logging.error(f"Error playing sound {sound_name}: {e}")
        finally:
            self.current_audio = None

    async def _generate_and_play_host_voice(self, text: str):
        try:
            logging.info(f"Generating host TTS for: {text}")
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="yl2ZDV1MzN4HbQJbMihG",
                output_format="mp3_44100_128",
                text=text,
                model_id="eleven_turbo_v2"
            )

            audio_data = b''
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_data += chunk
            
            with open(self.tts_output, 'wb') as f:
                f.write(audio_data)
            
            audio = AudioSegment.from_file(self.tts_output)
            temp_wav = f"{self.tts_output}_temp.wav"
            audio.export(temp_wav, format="wav")
            
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            duration = len(audio) / 1000.0
            await asyncio.sleep(duration)
            
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
            return True
                    
        except Exception as e:
            logging.error(f"Error generating/playing host TTS: {e}")
            return False
        finally:
            self.current_audio = None

    async def generate_host_commentary(self, event_type: str, context: dict) -> str:
        system_prompt = f"""You are the witty host of an adult trivia game show called Totally Not Trivial on Twitch. Your personality is sharp, sardonic, and playfully cruel - think British game show host meets insult comic. 
        Remember: This will be READ ALOUD, so write naturally for speech. Address players by their display names/nicknames (provided in the context), never their usernames. Be inclusive but still mock wrong answers.
        
        IMPORTANT: Be very clear about the difference between:
        - "games" (complete trivia sessions with multiple rounds)
        - "rounds" (individual questions within a game)
        - Do NOT confuse numbers in players' names with their statistics. Player statistics are provided separately in the context.
        - Keep your response to less than 220 characters, this is critical! 
        
        Keep your pronouns nuteral when addressing players and don't call players "beautiful disasters" or similar.
        No action commands, no asterisks, no stage directions, if it's an end_game scenario, ensure you sign off with something like 'thanks for playing! end_round is not the same, even if it's the last round, in this case you can say final round but don't sign off, there's still the end_game to come.'

        Event type: {event_type}
        Context: {json.dumps(context, indent=2)}

        Be witty but not crude. Reference player histories and running jokes when relevant."""

        try:
            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=1000,
                temperature=0.8,
                system=system_prompt,
                messages=[{"role": "user", "content": "Generate host commentary for speaking in under 220 characters"}]
            )
            
            return str(response.content[0].text)[:250]
        except Exception as e:
            logging.error(f"Error generating host commentary: {e}")
            return self.get_fallback_commentary(event_type)

    async def process_trivia_redeem(self, channel, username: str, message: str = None):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            if username in self.setup_pending_users:
                await channel.send(f"@{display_name}, you're already setting up a game!")
                return

            for existing_game in list(self.active_games.keys()):
                if existing_game in self.active_games:
                    del self.active_games[existing_game]

            self.setup_pending_users.clear()
            self.setup_timeout_tasks.clear()
            self.open_setup = False

            self.active_games[username] = {
                'awaiting_setup': True
            }

            self.setup_pending_users.add(username)
            timeout_task = asyncio.create_task(self.handle_setup_timeout(channel, username))
            self.setup_timeout_tasks[username] = timeout_task

            logging.info(f"Game initialization: active_games={self.active_games}, setup_pending_users={self.setup_pending_users}")
            
            await asyncio.sleep(1)
            
            chat_msg = (
                f"{display_name} is starting a new game of Totally Not Trivial! 🧠 ||  " 
                f"Categories: {', '.join(self.categories.keys())}  ||  "
                f"@{username} - Choose category and rounds (1-10) within 60 seconds  ||  e.g.: music 5"
            )
            
            await channel.send(chat_msg)
            await self.queue_audio('tts', {
                'text': f"All right everyone! {display_name} wants to test your knowledge! Get ready, while they pick our category! They have 60 seconds!"
            })
                
        except Exception as e:
            logging.error(f"Error in process_trivia_redeem: {e}")
            await channel.send("Sorry, something went wrong starting the trivia game!")
            if username in self.setup_pending_users:
                self.setup_pending_users.remove(username)
            if username in self.active_games:
                del self.active_games[username]

    async def get_player_history(self, username: str) -> dict:
        session = self.db_manager.get_session()
        try:
            stats = session.query(TriviaStats).filter_by(username=username).first()
            if stats:
                return {
                    'games_played': int(stats.games_played or 0),
                    'correct_answers': int(stats.correct_answers or 0),
                    'wrong_answers': int(stats.wrong_answers or 0),
                    'fastest_answers': int(stats.fastest_answers or 0),
                    'total_points': int(stats.total_points or 0),
                    'stats_description': 'These are the player statistics, not part of their name'
                }
            return {
                'games_played': 0,
                'correct_answers': 0,
                'wrong_answers': 0,
                'fastest_answers': 0,
                'total_points': 0,
                'stats_description': 'New player with no previous stats'
            }
        finally:
            session.close()

    async def handle_setup_response(self, channel, username: str, message: str):
        try:
            logging.info(f"Received setup response from {username}: '{message}'")
            logging.info(f"Current state: active_games={self.active_games}, setup_pending_users={self.setup_pending_users}")
            
            game_owner = next((owner for owner, game in self.active_games.items() 
                            if game.get('awaiting_setup')), None)
            
            if not game_owner:
                logging.info(f"No game awaiting setup found")
                return
                    
            game_data = self.active_games[game_owner]
            
            is_authorized = (
                username == game_owner or
                (game_data.get('open_setup', False) and self.open_setup)
            )
            
            if not is_authorized:
                logging.info(f"User {username} not authorized to setup game owned by {game_owner}")
                return
            
            cleaned_message = ''.join(c for c in message if c.isascii()).strip()
            parts = cleaned_message.lower().split()
            
            if len(parts) == 2 and parts[0] in self.categories and parts[1].isdigit():
                if game_owner in self.setup_timeout_tasks:
                    self.setup_timeout_tasks[game_owner].cancel()
                    del self.setup_timeout_tasks[game_owner]
            else:
                user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
                display_name = user_context.get('nickname', username)
                msg = f"Sorry {display_name}, I didn't catch that! Please pick a category and number of rounds!"
                await channel.send(msg)
                return

            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            category, rounds = parts
            
            if category not in self.categories:
                categories_list = ', '.join(self.categories.keys())
                msg = f"Sorry {display_name}, that's not a valid category! Your choices are: {categories_list}"
                await channel.send(msg)
                await self.queue_audio('tts', {'text': "Sorry, that's not a valid category. Try again!"})
                return

            try:
                num_rounds = int(rounds)
                if not 1 <= num_rounds <= 10:
                    raise ValueError()
            except ValueError:
                msg = f"Sorry {display_name}, rounds must be a number between 1 and 10!"
                await channel.send(msg)
                await self.queue_audio('tts', {'text': "The number of rounds must be between 1 and 10!"})
                return

            logging.info(f"Successfully processed setup from {username}: category={category}, rounds={num_rounds}")

            self.setup_pending_users.clear()
            self.setup_timeout_tasks.clear()
            self.open_setup = False
            
            if username != game_owner:
                game_data = self.active_games.pop(game_owner)
                self.active_games[username] = game_data
            
            await self.start_game(channel, username, category, num_rounds)
            
        except Exception as e:
            logging.error(f"Error in handle_setup_response: {e}")
            await channel.send(f"@{username}, sorry, something went wrong setting up the game!")
            if username in self.setup_pending_users:
                self.setup_pending_users.remove(username)

    async def handle_setup_timeout(self, channel, username: str):
        await asyncio.sleep(self.setup_timeout)

        if username in self.setup_pending_users:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            self.setup_pending_users.remove(username)
            
            if username in self.active_games:
                self.active_games[username].update({
                    'awaiting_setup': True,
                    'open_setup': True,
                    'original_owner': username
                })
                self.open_setup = True
            
            timeout_msg = f"Looks like {display_name} had some trouble! The game setup is now open to anyone! Can someone in chat give us a category and number of rounds!"
            await channel.send(timeout_msg)
            await self.queue_audio('tts', {'text': timeout_msg})

    async def start_game(self, channel, username: str, category: str, rounds: int):
        try:
            user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)
            
            category_id = self.categories[category]
            questions = await self.fetch_trivia_questions(category_id, rounds)
            
            if not questions:
                msg = f"Sorry {display_name}, I've lost my cue cards! Try again later!"
                await channel.send(msg)
                await self.queue_audio('tts', {'text': msg})
                del self.active_games[username]
                return
                    
            game_data = {
                'initiator': username,
                'questions': questions,
                'current_round': 0,
                'total_rounds': rounds,
                'category': category,
                'scores': {},
                'current_answers': {},
                'round_start_time': None,
                'answer_window_task': None,
                'participants': set(),
                'fastest_answers': [],
                'memorable_moments': []
            }
            
            self.active_games[username] = game_data

            host_context = {
                'initiator': display_name,
                'category': category,
                'rounds': rounds,
                'previous_games': await self.get_player_history(username)
            }

            logging.info(f"Generating host commentary for game start")
            intro_message = await self.generate_host_commentary('game_start', host_context)
            logging.info(f"Successfully generated host commentary: {intro_message[:50]}...")

            if self.current_audio:
                logging.info("Stopping current audio before game start")
                self.current_audio.stop()
                self.current_audio = None
            
            import gc
            gc.collect()
            
            await asyncio.sleep(1)
            
            await self.audio_queue.join()
            logging.info("Playing intro sound")
            await self.queue_audio('sound', {'name': 'intro', 'volume': 0.5})
            
            await self.send_companion_event('text-overlay', {
                'content': "🧠 TOTALLY NOT TRIVIAL 🧠",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '48px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#FFD700',
                    'position': 'absolute',
                    'width': '795px',
                    'padding': '25px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.9)',
                    'borderRadius': '15px',
                    'border': '4px solid #FFD700',
                    'boxShadow': '0 0 30px rgba(255, 215, 0, 0.6)'
                },
                'position': {
                    'top': '45px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 10000
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': f"Host: {display_name}",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '34px',
                    'fontWeight': '700',
                    'textAlign': 'left',
                    'color': '#FFFFFF',
                    'position': 'absolute',
                    'width': '720px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(40, 40, 60, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '175px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 9500
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': f"Category: {category.upper()}",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '32px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': '#FFFFFF',
                    'position': 'absolute',
                    'width': '720px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 40, 20, 0.85)',
                    'borderRadius': '12px',
                    'border': '2px solid #2ECC71'
                },
                'position': {
                    'top': '255px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 9000
            })

            await asyncio.sleep(3)
            await self.send_companion_event('text-overlay', {
                'content': "GET READY!",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '48px',
                    'fontWeight': '900',
                    'textAlign': 'center',
                    'color': '#E74C3C',
                    'position': 'absolute',
                    'width': '400px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.9)',
                    'borderRadius': '12px'
                },
                'position': {
                    'top': '390px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 6000
            })

            logging.info(f"Generating host TTS for: {intro_message}")
            response = await asyncio.to_thread(
                self.tts_client.text_to_speech.convert,
                voice_id="yl2ZDV1MzN4HbQJbMihG",
                output_format="mp3_44100_128",
                text=intro_message,
                model_id="eleven_flash_v2_5"
            )

            audio_data = b''
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_data += chunk
            
            with open(self.tts_output, 'wb') as f:
                f.write(audio_data)

            await asyncio.sleep(2)
            await channel.send(intro_message)
            
            audio = AudioSegment.from_file(self.tts_output)
            temp_wav = f"{self.tts_output}_temp.wav"
            audio.export(temp_wav, format="wav")
            
            wave_obj = sa.WaveObject.from_wave_file(temp_wav)
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            duration = len(audio) / 1000.0
            await asyncio.sleep(duration)
            
            try:
                os.remove(temp_wav)
            except Exception:
                pass

            await self.audio_queue.join()

            session = self.db_manager.get_session()
            try:
                game_record = TriviaGame(
                    initiator=username,
                    category=category,
                    rounds=rounds,
                    participants=[username],
                    round_results=[]
                )
                session.add(game_record)
                session.commit()
                game_data['game_id'] = game_record.id
            finally:
                session.close()

            await asyncio.sleep(1)
            
            await self.start_round(channel, username)
            
        except Exception as e:
            logging.error(f"Error starting game: {e}")
            await channel.send("Sorry, something went wrong starting the game!")
            if username in self.active_games:
                del self.active_games[username]

    async def load_custom_category_questions(self, category: str, amount: int) -> list:
        try:
            category_path = self.base_dir / 'redeems' / category.capitalize()
            if not category_path.exists():
                os.makedirs(category_path, exist_ok=True)
                logging.warning(f"{category.capitalize()} trivia directory did not exist, created at {category_path}")
                return []
                
            json_files = list(category_path.glob('*.json'))
            if not json_files:
                logging.warning(f"No JSON files found in the {category} trivia directory")
                return []
                
            json_file = random.choice(json_files)
            logging.info(f"Loading {category} trivia from: {json_file}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            questions = []
            
            if not isinstance(data, list):
                logging.error(f"{category.capitalize()} trivia JSON should be a list, found {type(data)}")
                return []
                
            if len(data) > amount:
                data = random.sample(data, amount)
            
            for item in data:
                if not isinstance(item, dict):
                    logging.warning(f"Skipping invalid question item: {item}")
                    continue
                    
                if not all(key in item for key in ['question', 'correct_answer', 'incorrect_answers']):
                    logging.warning(f"Skipping question with missing required fields: {item}")
                    continue
                    
                if not isinstance(item['incorrect_answers'], list) or len(item['incorrect_answers']) != 3:
                    logging.warning(f"Skipping question with invalid incorrect_answers: {item}")
                    continue
                    
                questions.append({
                    'question': html.unescape(item['question']),
                    'correct_answer': html.unescape(item['correct_answer']),
                    'incorrect_answers': [html.unescape(ans) for ans in item['incorrect_answers']]
                })
                
            return questions[:amount]
        except Exception as e:
            logging.error(f"Error loading {category} trivia questions: {e}")
            return []

    async def fetch_trivia_questions(self, category: Optional[int], amount: int) -> List[Dict]:
        try:
            if isinstance(category, str) and category in self.custom_categories:
                return await self.load_custom_category_questions(category, amount)
                
            base_url = "https://opentdb.com/api.php"
            params = {
                'amount': amount,
                'type': 'multiple'
            }
            if category:
                params['category'] = category

            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        questions = []
                        for q in data['results']:
                            questions.append({
                                'question': q['question'],
                                'correct_answer': q['correct_answer'],
                                'incorrect_answers': q['incorrect_answers']
                            })
                        return questions
                    else:
                        logging.error(f"Failed to fetch trivia questions: {response.status}")
                        return []
        except Exception as e:
            logging.error(f"Error fetching trivia questions: {e}")
            return []
        
    async def start_round(self, channel, username: str):
        try:
            game_data = self.active_games[username]
            current_round = game_data['current_round']
            
            question_data = game_data['questions'][current_round]
            correct_answer = html.unescape(question_data['correct_answer'])
            incorrect_answers = [html.unescape(a) for a in question_data['incorrect_answers']]
            
            options = [correct_answer] + incorrect_answers
            random.shuffle(options)
            
            correct_index = options.index(correct_answer)
            answer_letter = chr(65 + correct_index)
            
            game_data['current_question'] = {
                'question': html.unescape(question_data['question']),
                'options': options,
                'correct_answer': answer_letter,
                'correct_text': correct_answer
            }

            await self.queue_audio('tts', {'text': f"Round {current_round + 1}! Here's your question..."})
            await self.queue_audio('background', {'name': 'thinking', 'volume': 0.5})

            question_text = game_data['current_question']['question']
            
            chars_per_line = 50
            question_words = question_text.split()
            current_line_length = 0
            question_line_count = 1
            
            for word in question_words:
                if current_line_length + len(word) + 1 > chars_per_line:
                    question_line_count += 1
                    current_line_length = len(word)
                else:
                    current_line_length += len(word) + 1
            
            base_height = 100
            line_height = 40
            question_height = base_height + ((question_line_count - 1) * line_height)

            const_spacing = 30
            base_option_top = question_height + const_spacing + 130

            option_positions = [base_option_top]
            option_heights = []
            for option in options:
                chars_per_line = 50
                option_chars = len(option) + 3
                lines_needed = max(1, (option_chars + chars_per_line - 1) // chars_per_line)
                height = 70 + (max(0, lines_needed - 1) * 35)
                option_heights.append(height)
            
            for i in range(1, len(options)):
                position = option_positions[i-1] + option_heights[i-1] + 10
                option_positions.append(position)

            await self.send_companion_event('text-overlay', {
                'content': f"Round {current_round + 1} of {game_data['total_rounds']}",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '36px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#FFD700',
                    'position': 'absolute',
                    'width': '500px',
                    'padding': '15px 20px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '3px solid #FFD700',
                    'boxShadow': '0 0 15px rgba(255, 215, 0, 0.5)'
                },
                'position': {
                    'top': '45px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': self.answer_window * 1000
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': question_text,
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '32px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': 'white',
                    'position': 'absolute',
                    'width': '800px',
                    'minHeight': f'{question_height}px',
                    'padding': '20px',
                    'backgroundColor': 'rgba(40, 40, 60, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '130px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': self.answer_window * 1000
            })

            option_styles = [
                {'bg': 'rgba(231, 76, 60, 0.9)', 'border': '#E74C3C'},
                {'bg': 'rgba(46, 204, 113, 0.9)', 'border': '#2ECC71'},
                {'bg': 'rgba(52, 152, 219, 0.9)', 'border': '#3498DB'},
                {'bg': 'rgba(241, 196, 15, 0.9)', 'border': '#cfa10a'}
            ]

            for i, option in enumerate(options):
                letter = chr(65 + i)
                await asyncio.sleep(0.2)
                
                await self.send_companion_event('text-overlay', {
                    'content': f"{letter}. {option}",
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '28px',
                        'fontWeight': '600',
                        'textAlign': 'left',
                        'color': 'white',
                        'position': 'absolute',
                        'width': '800px',
                        'height': f'{option_heights[i]}px',
                        'padding': '20px',
                        'backgroundColor': option_styles[i]['bg'],
                        'borderRadius': '12px',
                        'border': f'2px solid {option_styles[i]["border"]}'
                    },
                    'position': {
                        'top': f'{option_positions[i]}px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': self.answer_window * 1000
                })

            timer_top = option_positions[-1] + option_heights[-1] + 40

            await asyncio.sleep(0.3)
            await self.send_companion_event('text-overlay', {
                'content': "⏱️ 30 seconds to answer!",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '24px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': 'white',
                    'position': 'absolute',
                    'width': '385px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(155, 89, 182, 0.9)',
                    'borderRadius': '12px',
                    'border': '2px solid #9B59B6'
                },
                'position': {
                    'top': f'{timer_top}px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': self.answer_window * 1000
            })

            question_display = (
                f"💡 Round {current_round + 1} / {game_data['total_rounds']}  ||  "
                f"Q: {game_data['current_question']['question']}  ||  "
                f"[A] {options[0]}  |  [B] {options[1]}  |  [C] {options[2]}  |  [D] {options[3]}  ||  "
                f"Type A, B, C, or D to answer!"
            )
            
            await channel.send(question_display)

            game_data['round_start_time'] = datetime.now()
            game_data['current_answers'] = {}
            
            session = self.db_manager.get_session()
            try:
                round_record = TriviaRound(
                    game_id=game_data['game_id'],
                    question=question_data['question'],
                    correct_answer=correct_answer,
                    options=options,
                    round_number=current_round + 1
                )
                session.add(round_record)
                session.commit()
                game_data['current_round_id'] = round_record.id
            finally:
                session.close()

            asyncio.create_task(self.handle_round_timeout(channel, username))

        except Exception as e:
            logging.error(f"Error starting round: {e}")
            await self.end_game(channel, username)

    async def handle_answer(self, channel, username: str, answer: str, game_owner: str):
        try:
            if game_owner not in self.active_games:
                return
            
            game_data = self.active_games[game_owner]
            if not game_data.get('round_start_time'):
                return
                
            if username in game_data['current_answers']:
                return
            
            valid_answer = None
            message_clean = answer.strip().lower()
            
            if len(message_clean) == 1 and message_clean in 'abcd':
                valid_answer = message_clean.upper()
            elif len(message_clean) == 2 and message_clean[0] in 'abcd' and not message_clean[1].isalnum():
                valid_answer = message_clean[0].upper()
            elif len(message_clean) == 3 and message_clean[0] in 'abcd' and not message_clean[1].isalnum() and not message_clean[2].isalnum():
                valid_answer = message_clean[0].upper()
            
            if valid_answer is None:
                return
            
            current_time = datetime.now()
            answer_time = (current_time - game_data['round_start_time']).total_seconds()
            
            if username not in game_data['scores']:
                game_data['scores'][username] = 0
                game_data['participants'].add(username)
                self.db_manager.update_trivia_stats(username, new_game=True)
            
            game_data['current_answers'][username] = {
                'answer': valid_answer,
                'time': answer_time,
                'timestamp': current_time
            }
            
            is_correct = valid_answer == game_data['current_question']['correct_answer']
            
            if is_correct:
                score_increment = max(10, int(30 - answer_time))
                game_data['scores'][username] += score_increment
                
                self.db_manager.update_trivia_stats(
                    username,
                    points_to_add=0,
                    correct=True,
                    answer_time=answer_time
                )
            else:
                self.db_manager.update_trivia_stats(
                    username,
                    points_to_add=0,
                    wrong=True
                )
            
            logging.info(f"User {username} answer processed: '{valid_answer}', is_correct: {is_correct}")
            
            game_data.setdefault('fastest_answers', []).append({
                'username': username,
                'time': answer_time,
                'round': game_data['current_round'] + 1,
                'correct': is_correct
            })
        
        except Exception as e:
            logging.error(f"Error handling answer: {e}", exc_info=True)

    async def handle_round_timeout(self, channel, username: str):
        try:
            game_data = self.active_games[username]
            await asyncio.sleep(22)
            
            if username in self.active_games and game_data.get('round_start_time'):
                audio_data = open(self.base_dir / 'sounds' / '10seconds.mp3', 'rb').read()
                with open(self.tts_output, 'wb') as f:
                    f.write(audio_data)
                
                audio = AudioSegment.from_file(self.tts_output)
                temp_wav = f"{self.tts_output}_temp.wav"
                audio.export(temp_wav, format="wav")
                
                wave_obj = sa.WaveObject.from_wave_file(temp_wav)
                play_obj = wave_obj.play()
                self.current_audio = play_obj
                
                duration = len(audio) / 1000.0
                await asyncio.sleep(duration)
                
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass
                    
                await asyncio.sleep(5 - duration)
                    
                if username in self.active_games and game_data.get('round_start_time'):
                    await self.queue_audio('sound', {'name': 'countdown', 'volume': 0.7})
                    
                await asyncio.sleep(5)
                    
                if username in self.active_games and game_data.get('round_start_time'):
                    game_data['round_start_time'] = None
                    
                    audio_data = open(self.base_dir / 'sounds' / 'timesup.mp3', 'rb').read()
                    with open(self.tts_output, 'wb') as f:
                        f.write(audio_data)
                    
                    audio = AudioSegment.from_file(self.tts_output)
                    temp_wav = f"{self.tts_output}_temp.wav"
                    audio.export(temp_wav, format="wav")
                    
                    wave_obj = sa.WaveObject.from_wave_file(temp_wav)
                    play_obj = wave_obj.play()
                    self.current_audio = play_obj
                    
                    duration = len(audio) / 1000.0
                    await asyncio.sleep(duration)
                    
                    try:
                        os.remove(temp_wav)
                    except Exception:
                        pass
                    
                    await self.end_round(channel, username)
                        
        except Exception as e:
            logging.error(f"Error in round timeout: {e}")

    async def end_round(self, channel, username: str):
        try:
            game_data = self.active_games[username]
            current_question = game_data['current_question']
            correct_answer = current_question['correct_answer']
            correct_text = current_question['correct_text']

            if self.current_audio:
                self.current_audio.stop()
            await self.audio_queue.join()

            correct_users = []
            wrong_users = []
            fastest_correct = None
            fastest_time = float('inf')

            for user, answer_data in game_data['current_answers'].items():
                is_correct = answer_data['answer'] == correct_answer
                answer_time = answer_data['time']
                
                if is_correct:
                    correct_users.append((user, answer_time))
                    if answer_time < fastest_time:
                        fastest_time = answer_time
                        fastest_correct = (user, answer_time)
                else:
                    wrong_users.append((user, answer_time))

            round_results = {
                'round_number': game_data['current_round'] + 1,
                'correct_users': [user for user, _ in correct_users],
                'wrong_users': [user for user, _ in wrong_users],
                'fastest_correct': fastest_correct[0] if fastest_correct else None,
                'fastest_time': fastest_correct[1] if fastest_correct else None
            }
            game_data.setdefault('round_results', []).append(round_results)

            session = self.db_manager.get_session()
            try:
                self.update_round_stats(session, game_data, correct_users, wrong_users, fastest_correct)
                session.commit()
            except Exception as e:
                session.rollback()
                logging.error(f"Error updating round stats: {e}")
            finally:
                session.close()

            correct_users_display = []
            for user, time in correct_users:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                correct_users_display.append((user_ctx.get('nickname', user), time))

            wrong_users_display = []
            for user, time in wrong_users:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                wrong_users_display.append((user_ctx.get('nickname', user), time))

            fastest_display = None
            if fastest_correct:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, fastest_correct[0])
                fastest_display = (user_ctx.get('nickname', fastest_correct[0]), fastest_correct[1])

            commentary_context = {
                'correct_users': correct_users_display,
                'wrong_users': wrong_users_display,
                'fastest_correct': fastest_display,
                'correct_answer': correct_text,
                'round': game_data['current_round'] + 1,
                'total_rounds': game_data['total_rounds']
            }

            round_summary = await self.generate_host_commentary('round_end', commentary_context)

            await self.send_companion_event('text-overlay', {
                'content': f"Round {game_data['current_round'] + 1} Results",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '36px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#FFD700',
                    'position': 'absolute',
                    'width': '500px',
                    'padding': '15px 20px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '3px solid #FFD700'
                },
                'position': {
                    'top': '45px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 10500
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': f"Correct Answer: {correct_answer}. {correct_text}",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '28px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': '#FFFFFF',
                    'position': 'absolute',
                    'width': '900px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 40, 20, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #2ECC71'
                },
                'position': {
                    'top': '130px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 10000
            })

            correct_count = len(correct_users)
            wrong_count = len(wrong_users)
            
            await asyncio.sleep(0.5)
            stats_content = "📊 Statistics"
            await self.send_companion_event('text-overlay', {
                'content': stats_content,
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '24px',
                    'fontWeight': '700',
                    'textAlign': 'left',
                    'color': '#3498DB',
                    'position': 'absolute',
                    'width': '400px',
                    'padding': '10px 15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '245px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 9500
            })

            await asyncio.sleep(0.5)
            if game_data['current_answers']:
                accuracy = (correct_count / len(game_data['current_answers'])) * 100
                stats_details = (
                    f"✅ Correct: {correct_count}\n"
                    f"❌ Wrong: {wrong_count}\n"
                    f"🎯 Accuracy: {accuracy:.1f}%"
                )
            else:
                stats_details = "No answers submitted!"

            await self.send_companion_event('text-overlay', {
                'content': stats_details,
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '22px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': 'white',
                    'position': 'absolute',
                    'width': '350px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.9)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '300px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 9000
            })

            await asyncio.sleep(0.5)
            if correct_users:
                display_correct_users = []
                for user, _ in correct_users:
                    user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                    display_correct_users.append(user_ctx.get('nickname', user))
                
                await self.send_companion_event('text-overlay', {
                    'content': "🏆 Correct Players:",
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '24px',
                        'fontWeight': '700',
                        'textAlign': 'left',
                        'color': '#F1C40F',
                        'position': 'absolute',
                        'width': '400px',
                        'padding': '10px 15px',
                        'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                        'borderRadius': '12px',
                        'border': '2px solid #F1C40F'
                    },
                    'position': {
                        'top': '400px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 8500
                })

                players_list = ', '.join(display_correct_users[:10])
                if len(display_correct_users) > 10:
                    players_list += f" and {len(display_correct_users) - 10} more"

                await asyncio.sleep(0.5)
                await self.send_companion_event('text-overlay', {
                    'content': players_list,
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '20px',
                        'fontWeight': '600',
                        'textAlign': 'left',
                        'color': 'white',
                        'position': 'absolute',
                        'width': '600px',
                        'padding': '15px',
                        'backgroundColor': 'rgba(20, 20, 40, 0.9)',
                        'borderRadius': '12px',
                        'border': '2px solid #F1C40F'
                    },
                    'position': {
                        'top': '455px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 8000
                })
            else:
                await self.send_companion_event('text-overlay', {
                    'content': "💥 No Correct Answers! 💥",
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '28px',
                        'fontWeight': '700',
                        'textAlign': 'left',
                        'color': '#E74C3C',
                        'position': 'absolute',
                        'width': '520px',
                        'padding': '15px',
                        'backgroundColor': 'rgba(40, 20, 20, 0.95)',
                        'borderRadius': '12px',
                        'border': '3px solid #E74C3C'
                    },
                    'position': {
                        'top': '430px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 7500
                })

            display_correct_users_final = []
            for user, _ in correct_users:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                display_correct_users_final.append(user_ctx.get('nickname', user))

            results_message = f"The correct answer was [{correct_answer}] {correct_text}  ||  "
            if display_correct_users_final:
                results_message += f"Correct: {', '.join(display_correct_users_final)}  ||  "
                if fastest_correct:
                    user_context = await asyncio.to_thread(self.db_manager.get_user_context, fastest_correct[0])
                    display_name = user_context.get('nickname', fastest_correct[0])
                    results_message += f"Fastest: {display_name} ({fastest_correct[1]:.1f}s)"
            else:
                results_message += "No correct answers!"
            
            await channel.send(results_message)
            await self.queue_audio('tts', {'text': round_summary})
            await self.audio_queue.join()

            game_data['current_round'] += 1
            
            if game_data['current_round'] >= game_data['total_rounds']:
                await self.end_game(channel, username)
            else:
                await asyncio.sleep(1)
                await self.start_round(channel, username)

        except Exception as e:
            logging.error(f"Error ending round: {e}")
            await self.end_game(channel, username)

    async def _process_tts(self, text: str) -> bytes:
        response = await asyncio.to_thread(
            self.tts_client.text_to_speech.convert,
            voice_id="yl2ZDV1MzN4HbQJbMihG",
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_turbo_v2"
        )

        audio_data = b''
        for chunk in response:
            if isinstance(chunk, bytes):
                audio_data += chunk
        return audio_data

    async def play_tts_audio(self, audio_data: bytes):
        with open(self.tts_output, 'wb') as f:
            f.write(audio_data)

        audio = AudioSegment.from_file(self.tts_output)
        temp_wav = f"{self.tts_output}_temp.wav"
        audio.export(temp_wav, format="wav")
        
        wave_obj = sa.WaveObject.from_wave_file(temp_wav)
        play_obj = wave_obj.play()
        self.current_audio = play_obj
        
        duration = len(audio) / 1000.0
        await asyncio.sleep(duration)
        
        try:
            os.remove(temp_wav)
        except Exception:
            pass

    def update_round_stats(self, session, game_data, correct_users, wrong_users, fastest_correct):
        round_record = session.query(TriviaRound).get(game_data['current_round_id'])
        if round_record:
            round_record.fastest_answer = fastest_correct[0] if fastest_correct else None
            round_record.answer_times = {
                user: data['time'] 
                for user, data in game_data['current_answers'].items()
            }
            round_record.correct_users = [user for user, _ in correct_users]
            round_record.wrong_users = [user for user, _ in wrong_users]

    def update_user_stats(self, session, game_data, correct_users, fastest_correct):
        try:
            participants = list(game_data['participants'])
            for username in participants:
                stats = session.query(TriviaStats).filter_by(username=username).first()
                if not stats:
                    stats = TriviaStats(
                        username=username,
                        correct_answers=0,
                        wrong_answers=0,
                        fastest_answers=0,
                        games_played=0,
                        total_points=0
                    )
                    session.add(stats)
                
                if not hasattr(game_data, 'recorded_game_participation'):
                    game_data['recorded_game_participation'] = set()
                    
                if username not in game_data['recorded_game_participation']:
                    stats.games_played += 1
                    game_data['recorded_game_participation'].add(username)
                    
                stats.total_points += game_data['scores'].get(username, 0)
                stats.last_played = datetime.now()

                if username in [user for user, _ in correct_users]:
                    stats.correct_answers += 1
                elif username in game_data['current_answers']:
                    stats.wrong_answers += 1
                    
                if fastest_correct and fastest_correct[0] == username:
                    stats.fastest_answers += 1

                self.commit_with_retry(session)
                
        except Exception as e:
            logging.error(f"Error updating user stats: {e}")
            session.rollback()

    def commit_with_retry(self, session, max_retries=3):
        for attempt in range(max_retries):
            try:
                session.commit()
                return True
            except Exception as e:
                logging.error(f"Database commit failed (attempt {attempt + 1}): {e}")
                session.rollback()
                if attempt == max_retries - 1:
                    raise
        return False

    async def end_game(self, channel, username: str):
        try:
            logging.info(f"Starting end_game for {username}")
            if username not in self.active_games:
                logging.warning(f"Game for {username} not found in active_games")
                return
                
            game_data = self.active_games[username]
            
            if self.current_audio:
                logging.info("Stopping current audio in end_game")
                self.current_audio.stop()
                self.current_audio = None
            
            await self.audio_queue.join()
            logging.info("Audio queue empty")

            sorted_scores = sorted(
                [(user, score) for user, score in game_data['scores'].items()],
                key=lambda x: x[1],
                reverse=True
            )
            
            winner = sorted_scores[0][0] if sorted_scores else None
            if winner:
                winner_ctx = await asyncio.to_thread(self.db_manager.get_user_context, winner)
                winner_display = winner_ctx.get('nickname', winner)
            else:
                winner_display = None

            session = self.db_manager.get_session()
            try:
                game_record = session.query(TriviaGame).get(game_data['game_id'])
                if game_record:
                    game_record.end_time = datetime.now()
                    game_record.winner = winner
                    game_record.participants = list(game_data['participants'])
                    game_record.final_scores = {user: score for user, score in sorted_scores}
                    game_record.total_players = len(game_data['participants'])
                    
                    for user, score in sorted_scores:
                        logging.info(f"END GAME: Adding {score} points to {user}'s total")
                        self.db_manager.update_trivia_stats(
                            user,
                            points_to_add=score,
                            correct=False,
                            wrong=False
                        )
                    
                    session.commit()
                    
            except Exception as e:
                session.rollback()
                logging.error(f"Error updating game record: {e}")
            finally:
                session.close()

            await self.queue_audio('sound', {'name': 'drumroll', 'volume': 0.3})
            await self.send_companion_event('text-overlay', {
                'content': "🎮 GAME OVER 🎮",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '38px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#FFD700',
                    'position': 'absolute',
                    'width': '440px',
                    'padding': '20px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '3px solid #FFD700'
                },
                'position': {
                    'top': '45px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 11000
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': "👑 CHAMPION 👑",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '38px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#9B59B6',
                    'position': 'absolute',
                    'width': '440px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #9B59B6'
                },
                'position': {
                    'top': '150px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 10500
            })

            await asyncio.sleep(0.5)
            if winner_display:
                await self.send_companion_event('text-overlay', {
                    'content': winner_display,
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '36px',
                        'fontWeight': '700',
                        'textAlign': 'left',
                        'color': '#FFD700',
                        'position': 'absolute',
                        'width': '600px',
                        'padding': '15px',
                        'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                        'borderRadius': '12px',
                        'border': '2px solid #FFD700'
                    },
                    'position': {
                        'top': '240px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 10000
                })

                await asyncio.sleep(0.5)
                await self.send_companion_event('text-overlay', {
                    'content': f"Score: {sorted_scores[0][1]}",
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '28px',
                        'fontWeight': '600',
                        'textAlign': 'left',
                        'color': '#2ECC71',
                        'position': 'absolute',
                        'width': '200px',
                        'padding': '12px',
                        'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                        'borderRadius': '12px',
                        'border': '2px solid #2ECC71'
                    },
                    'position': {
                        'top': '320px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 9500
                })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': "Final Standings",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '28px',
                    'fontWeight': '700',
                    'textAlign': 'left',
                    'color': '#3498DB',
                    'position': 'absolute',
                    'width': '400px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '400px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 9000
            })

            base_top = 470
            for i, (user, score) in enumerate(sorted_scores[:5]):
                await asyncio.sleep(0.2)
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                display_name = user_ctx.get('nickname', user)
                
                border_color = '#CD7F32'
                if i == 0:
                    border_color = '#FFD700'
                elif i == 1:
                    border_color = '#C0C0C0'
                    
                await self.send_companion_event('text-overlay', {
                    'content': f"{i+1}. {display_name}: {score}",
                    'style': {
                        'fontFamily': 'Montserrat',
                        'fontSize': '24px',
                        'fontWeight': '600',
                        'textAlign': 'left',
                        'color': 'white',
                        'position': 'absolute',
                        'width': '400px',
                        'padding': '12px',
                        'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                        'borderRadius': '10px',
                        'border': f'2px solid {border_color}'
                    },
                    'position': {
                        'top': f'{base_top + (i * 62)}px',
                        'left': '45px'
                    },
                    'animateIn': 'fadeInLeft',
                    'animateOut': 'fadeOutLeft',
                    'duration': 8000 - (i * 200)
                })

            score_display_list = []
            for user, score in sorted_scores[:5]:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                score_display_list.append(f"{user_ctx.get('nickname', user)}: {score}")
            score_display = "Final Scores  ||  " + "  |  ".join(score_display_list)
            await channel.send(score_display)

            scores_with_display = []
            for user, score in sorted_scores:
                user_ctx = await asyncio.to_thread(self.db_manager.get_user_context, user)
                scores_with_display.append((user_ctx.get('nickname', user), score))

            game_summary_context = {
                'winner': winner_display,
                'scores': scores_with_display,
                'participants': len(game_data['participants']),
                'fastest_answers': game_data.get('fastest_answers', []),
                'memorable_moments': game_data.get('memorable_moments', [])
            }

            end_commentary = await self.generate_host_commentary('game_end', game_summary_context)
            await self.queue_audio('tts', {'text': end_commentary})
            await self.audio_queue.join()

            await self.queue_audio('sound', {'name': 'outro', 'volume': 0.6})

            await asyncio.sleep(3)

            await self.send_companion_event('text-overlay', {
                'content': "Thanks for Playing! 💛",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '38px',
                    'fontWeight': '800',
                    'textAlign': 'left',
                    'color': '#FFD700',
                    'position': 'absolute',
                    'width': '520px',
                    'padding': '25px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '15px',
                    'border': '3px solid #FFD700'
                },
                'position': {
                    'top': '45px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 7000
            })

            await asyncio.sleep(0.5)
            await self.send_companion_event('text-overlay', {
                'content': f"Players: {len(game_data['participants'])} | Questions: {game_data['total_rounds']}",
                'style': {
                    'fontFamily': 'Montserrat',
                    'fontSize': '24px',
                    'fontWeight': '600',
                    'textAlign': 'left',
                    'color': '#3498DB',
                    'position': 'absolute',
                    'width': '600px',
                    'padding': '15px',
                    'backgroundColor': 'rgba(20, 20, 40, 0.95)',
                    'borderRadius': '12px',
                    'border': '2px solid #3498DB'
                },
                'position': {
                    'top': '170px',
                    'left': '45px'
                },
                'animateIn': 'fadeInLeft',
                'animateOut': 'fadeOutLeft',
                'duration': 6500
            })

            await asyncio.sleep(self.sound_durations['outro'] - 3.5)

            if username in self.active_games:
                del self.active_games[username]

            for user in list(self.setup_pending_users):
                self.setup_pending_users.remove(user)
                
            for task_key in list(self.setup_timeout_tasks.keys()):
                try:
                    self.setup_timeout_tasks[task_key].cancel()
                except Exception:
                    pass
                del self.setup_timeout_tasks[task_key]
                
            self.open_setup = False

            logging.info(f"Game ended. Final state: active_games={self.active_games}, setup_pending_users={self.setup_pending_users}")


        except Exception as e:
            logging.error(f"Error in end_game: {e}", exc_info=True)
        finally:
            logging.info("Performing final cleanup in end_game")
            if username in self.active_games:
                del self.active_games[username]
            
            if self.current_audio:
                try:
                    self.current_audio.stop()
                except Exception:
                    pass
                self.current_audio = None
                
            import gc
            gc.collect()
            
            logging.info("End game cleanup complete")

    def get_fallback_commentary(self, event_type: str) -> str:
        fallbacks = {
            'game_start': "Welcome to another round of Totally Not Trivial! Let's see who's got more than just looks going for them!",
            'correct_answer': "Well, well! Someone's been paying attention!",
            'wrong_answer': "Oh dear... I've seen better answers from a Magic 8 Ball!",
            'round_end': "Let's see who's still standing after that massacre!",
            'game_end': "That's all folks! Some of you might want to consider reading a book once in a while!"
        }
        return fallbacks.get(event_type, "The show must go on!")

    async def cleanup_audio(self):
        try:
            logging.info("Starting audio cleanup")
            if self.current_audio:
                logging.info("Stopping current audio")
                try:
                    self.current_audio.stop()
                except Exception as e:
                    logging.error(f"Error stopping audio: {e}")
                finally:
                    self.current_audio = None
                    
            for task in list(self.setup_timeout_tasks.values()):
                logging.info("Canceling setup timeout task")
                try:
                    task.cancel()
                except Exception:
                    pass
            self.setup_timeout_tasks.clear()
            self.setup_pending_users.clear()
            self.open_setup = False
            
            logging.info(f"Audio queue size before clearing: {self.audio_queue.qsize()}")
            while not self.audio_queue.empty():
                try:
                    await self.audio_queue.get()
                    self.audio_queue.task_done()
                except Exception:
                    pass
                    
            if self.audio_task and not self.audio_task.done():
                logging.info("Canceling audio task")
                try:
                    self.audio_task.cancel()
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logging.error(f"Error canceling audio task: {e}")
            
            import gc
            gc.collect()
            
            logging.info("Audio cleanup complete")
                        
        except Exception as e:
            logging.error(f"Error cleaning up audio: {e}", exc_info=True)