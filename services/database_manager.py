import time
from pathlib import Path
import time
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, scoped_session
import logging
from typing import Optional, Dict, List, Tuple
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Base, User, CustomInfo, Nickname, StinkHistory, GameHistory, EdgeStreak, TriviaGame, TriviaRound, TriviaStats
from config import BASE_DIR

class DatabaseManager:
    def __init__(self, database_url=None, max_retries=3, streamer_name=None):
        if database_url is None:
            data_dir = BASE_DIR / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{data_dir}/bot_data.db"
            
        self.streamer_name = streamer_name
        for attempt in range(max_retries):
            try:
                self.engine = create_engine(database_url)
                Base.metadata.create_all(self.engine)
                session_factory = sessionmaker(bind=self.engine)
                self.Session = scoped_session(session_factory)

                logging.info("Database connection established successfully")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                    raise
                logging.warning(f"Database connection attempt {attempt + 1} failed, retrying...")
                time.sleep(1)

    def get_session(self):
        return self.Session()

    def get_or_create_user(self, username: str) -> User:
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if not user:
                user = User(
                    username=username.lower(),
                    conversation_history=[],
                    favorite_emotes={},
                    active_times={}
                )
                session.add(user)
                session.commit()
            return user
        except Exception as e:
            session.rollback()
            logging.error(f"Error in get_or_create_user: {e}")
            raise
        finally:
            session.close()
            
    def update_user_profile(self, username: str, **kwargs):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if not user:
                user = User(username=username.lower())
                session.add(user)

            for field in ['first_seen', 'last_seen']:
                if field in kwargs and isinstance(kwargs[field], str):
                    kwargs[field] = datetime.fromisoformat(kwargs[field])

            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error in update_user_profile: {e}")
            raise
        finally:
            session.close()

    def set_user_color(self, username: str, color: str):
        if not color:
            return

        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if not user:
                user = User(username=username.lower(), color=color)
                session.add(user)
            else:
                user.color = color
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error setting user color: {e}")
        finally:
            session.close()

    def get_user_context(self, username: str) -> dict:
        session = self.get_session()
        try:
            username = username.lower()
            context = {
                'username': username,
                'messages_count': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now()
            }
            
            user = session.query(User).filter_by(username=username).first()
            if user:
                context.update({
                    'messages_count': user.messages_count or 0,
                    'first_seen': user.first_seen,
                    'last_seen': user.last_seen,
                    'responded_to_count': user.responded_to_count or 0,
                    'questions_asked': user.questions_asked or 0
                })

                if user.color:
                    context['color'] = user.color
                else:
                    context['color'] = None

                if user.favorite_emotes:
                    context['emote_preferences'] = dict(
                        sorted(user.favorite_emotes.items(),
                              key=lambda x: x[1],
                              reverse=True)[:5]
                    )

                if user.active_times:
                    context['activity'] = dict(
                        sorted(user.active_times.items(), 
                              key=lambda x: x[1], 
                              reverse=True)[:3]
                    )

                if user.conversation_history:
                    context['recent_conversations'] = user.conversation_history[-5:]

                if user.custom_prompt:
                    context['custom_prompt'] = user.custom_prompt

                context['bot_engagement_score'] = user.bot_engagement_score or 0
                context['last_engaged_with_bot'] = user.last_engaged_with_bot
                context['bot_interactions_count'] = user.bot_interactions_count or 0

            custom_info = session.query(CustomInfo).filter_by(username=username).all()
            if custom_info:
                context['custom_info'] = {info.info_type: info.value for info in custom_info}

            nickname = session.query(Nickname).filter_by(username=username).first()
            if nickname and nickname.nickname != username:
                context['nickname'] = nickname.nickname

            stink_history = self.get_stink_history(username)
            if stink_history:
                latest_stink = stink_history[-1]
                if len(stink_history) > 1:
                    average_stink = sum(entry['value'] for entry in stink_history) / len(stink_history)
                else:
                    average_stink = latest_stink['value']
                
                context['stink'] = {
                    'current': latest_stink['value'],
                    'average': round(average_stink, 1),
                    'history': stink_history[-5:]
                }

            return context

        except Exception as e:
            logging.error(f"Error in get_user_context: {e}", exc_info=True)
            return {
                'username': username,
                'error': str(e),
                'messages_count': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now()
            }
        finally:
            session.close()

    def add_custom_info(self, username: str, info_dict: dict):
        session = self.get_session()
        try:
            for info_type, value in info_dict.items():
                existing = session.query(CustomInfo).filter_by(
                    username=username.lower(),
                    info_type=info_type
                ).first()
                
                if existing:
                    existing.value = str(value)
                else:
                    custom_info = CustomInfo(
                        username=username.lower(),
                        info_type=info_type,
                        value=str(value)
                    )
                    session.add(custom_info)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error in add_custom_info: {e}")
            raise
        finally:
            session.close()

    def delete_specific_info(self, username: str, info_type: str) -> bool:
        session = self.get_session()
        try:
            result = session.query(CustomInfo).filter_by(
                username=username.lower(),
                info_type=info_type.lower()
            ).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logging.error(f"Error in delete_specific_info: {e}")
            raise
        finally:
            session.close()

    def delete_all_info(self, username: str) -> int:
        session = self.get_session()
        try:
            result = session.query(CustomInfo).filter_by(
                username=username.lower()
            ).delete()
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logging.error(f"Error in delete_all_info: {e}")
            raise
        finally:
            session.close()

    def add_nickname(self, username: str, nickname: str):
        session = self.get_session()
        try:
            existing = session.query(Nickname).filter_by(username=username.lower()).first()
            if existing:
                existing.nickname = nickname
            else:
                new_nickname = Nickname(username=username.lower(), nickname=nickname)
                session.add(new_nickname)
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error in add_nickname: {e}")
            raise
        finally:
            session.close()

    def set_custom_prompt(self, username: str, custom_prompt: str):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if not user:
                user = User(username=username.lower(), custom_prompt=custom_prompt)
                session.add(user)
            else:
                user.custom_prompt = custom_prompt
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error setting custom prompt: {e}")
            raise
        finally:
            session.close()

    def remove_custom_prompt(self, username: str):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if user:
                user.custom_prompt = None
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logging.error(f"Error removing custom prompt: {e}")
            raise
        finally:
            session.close()

    def add_stink_history(self, username: str, stink_value: int) -> None:
        session = self.get_session()
        try:
            stink_entry = StinkHistory(
                username=username.lower(),
                value=stink_value,
                timestamp=datetime.now()
            )
            session.add(stink_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error adding stink history: {e}")
            raise
        finally:
            session.close()

    def get_stink_history(self, username: str) -> List[Dict]:
        session = self.get_session()
        try:
            entries = session.query(StinkHistory)\
                .filter_by(username=username.lower())\
                .order_by(StinkHistory.timestamp)\
                .all()
            
            return [{
                'value': entry.value,
                'timestamp': entry.timestamp.isoformat()
            } for entry in entries]
        except Exception as e:
            logging.error(f"Error getting stink history: {e}")
            return []
        finally:
            session.close()

    def track_user_interaction(self, username: str, message: str, bot_response: str):
        session = self.get_session()
        try:
            user = self.get_or_create_user(username)

            current_history = user.conversation_history or []
            current_history.append({
                'timestamp': datetime.now().isoformat(),
                'user': message,
                'bot': bot_response
            })

            if len(current_history) > 20:
                current_history = current_history[-20:]

            self.update_user_profile(
                username,
                conversation_history=current_history,
                last_seen=datetime.now(),
                messages_count=(user.messages_count or 0) + 1
            )

        except Exception as e:
            logging.error(f"Error tracking interaction: {e}")
            session.rollback()
        finally:
            session.close()
    
    def record_game_result(self, word: str, winner: str = None):
        session = self.get_session()
        try:
            game_entry = GameHistory(word=word, winner=winner)
            session.add(game_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error recording game result: {e}")
        finally:
            session.close()

    def get_recent_words(self, limit=30) -> list:
        session = self.get_session()
        try:
            rows = (session.query(GameHistory)
                    .order_by(GameHistory.timestamp.desc())
                    .limit(limit)
                    .all())
            return [row.word for row in rows]
        except Exception as e:
            logging.error(f"Error fetching recent words: {e}")
            return []
        finally:
            session.close()

    def remove_word(self, word: str) -> bool:
        session = self.get_session()
        try:
            result = session.query(GameHistory).filter_by(word=word.lower()).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logging.error(f"Error removing word: {e}")
            return False
        finally:
            session.close()

    def get_edge_stats(self, username: str) -> Optional[EdgeStreak]:
        session = self.get_session()
        try:
            return session.query(EdgeStreak).filter_by(username=username.lower()).first()
        finally:
            session.close()

    def update_edge_stats(self, username: str, current_streak: int, busted: bool = False):
        session = self.get_session()
        try:
            logging.info(f"Updating edge stats for {username} - Streak: {current_streak}, Busted: {busted}")
            stats = session.query(EdgeStreak).filter_by(username=username.lower()).first()
            if not stats:
                logging.info(f"Creating new edge stats record for {username}")
                stats = EdgeStreak(
                    username=username.lower(),
                    session_start=datetime.now() if not busted else None
                )
                session.add(stats)
            
            stats.total_edges += 1
            
            if busted:
                stats.total_busts += 1
                stats.last_streak = current_streak - 1
                stats.session_start = None
                logging.info(f"User {username} busted. Session cleared. Total busts: {stats.total_busts}")
            else:
                if stats.session_start is None:
                    stats.session_start = datetime.now()
                    logging.info(f"Starting new session for {username}")
                
                if current_streak > stats.highest_streak:
                    stats.highest_streak = current_streak
                    logging.info(f"New highest streak for {username}: {current_streak}")
                
                session_length = current_streak
                if session_length > stats.longest_session:
                    stats.longest_session = session_length

            session.commit()
            logging.info(f"Successfully updated edge stats for {username}")
            return stats
        except Exception as e:
            logging.error(f"Error updating edge stats: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_edge_leaderboard(self) -> List[EdgeStreak]:
        session = self.get_session()
        try:
            return session.query(EdgeStreak)\
                .order_by(EdgeStreak.highest_streak.desc())\
                .limit(5)\
                .all()
        finally:
            session.close()

    def get_active_streaks(self) -> Dict[str, int]:
        session = self.get_session()
        try:
            active_users = session.query(EdgeStreak)\
                .filter(EdgeStreak.session_start.isnot(None))\
                .all()
            
            return {
                user.username: user.total_edges - user.total_busts
                for user in active_users
            }
        finally:
            session.close()

    def get_or_create_trivia_stats(self, username: str) -> TriviaStats:
        session = self.get_session()
        try:
            stats = session.query(TriviaStats).filter_by(username=username.lower()).first()
            if not stats:
                stats = TriviaStats(
                    username=username.lower(),
                    correct_answers=0,
                    wrong_answers=0,
                    fastest_answers=0,
                    games_played=0,
                    total_points=0
                )
                session.add(stats)
                session.commit()
            return stats
        except Exception as e:
            session.rollback()
            logging.error(f"Error in get_or_create_trivia_stats: {e}")
            raise
        finally:
            session.close()

    def update_trivia_stats(self, username: str, points_to_add: int = 0, 
                        correct: bool = False, wrong: bool = False,
                        answer_time: float = None, new_game: bool = False):
        session = self.get_session()
        try:
            stats = session.query(TriviaStats).filter_by(username=username.lower()).first()
            if not stats:
                stats = TriviaStats(
                    username=username.lower(),
                    correct_answers=0,
                    wrong_answers=0,
                    fastest_answers=None,
                    games_played=0,
                    total_points=0
                )
                session.add(stats)
            
            if new_game:
                stats.games_played += 1
            
            if correct:
                stats.correct_answers += 1

                if answer_time is not None:
                    if stats.fastest_answers is None or answer_time < stats.fastest_answers:
                        stats.fastest_answers = answer_time
                        logging.info(f"New personal best for {username}: {answer_time:.2f}s")
            
            if wrong:
                stats.wrong_answers += 1

            if points_to_add > 0:
                stats.total_points += points_to_add
                logging.info(f"Added {points_to_add} points to {username}, new total: {stats.total_points}")
            
            stats.last_played = datetime.now()
            
            session.commit()
            return stats
        except Exception as e:
            session.rollback()
            logging.error(f"Error updating trivia stats: {e}")
            raise
        finally:
            session.close()

    def create_trivia_game(self, initiator: str, category: str, rounds: int) -> int:
        session = self.get_session()
        try:
            game = TriviaGame(
                initiator=initiator.lower(),
                category=category,
                rounds=rounds,
                participants=[initiator.lower()],
                round_results=[],
                total_players=1
            )
            session.add(game)
            session.commit()
            return game.id
        except Exception as e:
            session.rollback()
            logging.error(f"Error creating trivia game: {e}")
            raise
        finally:
            session.close()

    def record_trivia_round(self, game_id: int, question: str, correct_answer: str, 
                           options: List[str], round_number: int) -> int:
        session = self.get_session()
        try:
            round_record = TriviaRound(
                game_id=game_id,
                question=question,
                correct_answer=correct_answer,
                options=options,
                round_number=round_number
            )
            session.add(round_record)
            session.commit()
            return round_record.id
        except Exception as e:
            session.rollback()
            logging.error(f"Error recording trivia round: {e}")
            raise
        finally:
            session.close()

    def update_trivia_round(self, round_id: int, fastest_answer: str = None, 
                           answer_times: Dict = None, correct_users: List = None, 
                           wrong_users: List = None):
        session = self.get_session()
        try:
            round_record = session.query(TriviaRound).get(round_id)
            if round_record:
                if fastest_answer is not None:
                    round_record.fastest_answer = fastest_answer
                if answer_times is not None:
                    round_record.answer_times = answer_times
                if correct_users is not None:
                    round_record.correct_users = correct_users
                if wrong_users is not None:
                    round_record.wrong_users = wrong_users
                session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error updating trivia round: {e}")
            raise
        finally:
            session.close()

    def complete_trivia_game(self, game_id: int, winner: str = None, 
                            participants: List[str] = None):
        session = self.get_session()
        try:
            game = session.query(TriviaGame).get(game_id)
            if game:
                game.end_time = datetime.now()
                if winner:
                    game.winner = winner
                if participants:
                    game.participants = participants
                    game.total_players = len(participants)
                session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error completing trivia game: {e}")
            raise
        finally:
            session.close()

    def get_all_users(self):
        session = self.get_session()
        try:
            return session.query(User).all()
        except Exception as e:
            session.rollback()
            logging.error(f"Error in get_all_users: {e}")
            return []
        finally:
            session.close()

    def track_bot_engagement(self, username: str, engaged: bool):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username.lower()).first()
            if not user:
                user = User(username=username.lower())
                session.add(user)

            if engaged:
                user.bot_engagement_score = (user.bot_engagement_score or 0) + 1
                user.last_engaged_with_bot = datetime.now()
            else:
                user.bot_engagement_score = (user.bot_engagement_score or 0) - 1

            user.bot_interactions_count = (user.bot_interactions_count or 0) + 1
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error tracking bot engagement: {e}")
        finally:
            session.close()

    def close(self):
        try:
            self.Session.remove()
            self.engine.dispose()
            logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")