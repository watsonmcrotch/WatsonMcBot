from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Index, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    color = Column(String, nullable=True)
    messages_count = Column(Integer, default=0)
    first_seen = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now)
    conversation_history = Column(JSON, default=list)
    favorite_emotes = Column(JSON, default=dict)
    active_times = Column(JSON, default=dict)
    responded_to_count = Column(Integer, default=0)
    questions_asked = Column(Integer, default=0)
    custom_prompt = Column(String, nullable=True)
    bot_engagement_score = Column(Integer, default=0)
    last_engaged_with_bot = Column(DateTime, nullable=True)
    bot_interactions_count = Column(Integer, default=0)

    __table_args__ = (Index('idx_username', 'username'),)

class GameHistory(Base):
    __tablename__ = 'game_history'

    id = Column(Integer, primary_key=True)
    word = Column(String, nullable=False)
    winner = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

class EdgeStreak(Base):
    __tablename__ = 'edge_streaks'

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    highest_streak = Column(Integer, default=0)
    total_busts = Column(Integer, default=0)
    last_streak = Column(Integer, default=0)
    total_edges = Column(Integer, default=0)
    longest_session = Column(Integer, default=0)
    session_start = Column(DateTime, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)
    current_streak = Column(Integer, default=0)

class CustomInfo(Base):
    __tablename__ = 'custom_info'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    info_type = Column(String, nullable=False)
    value = Column(String)
    
    user = relationship("User", backref="custom_info")

    __table_args__ = (Index('idx_custom_info_username', 'username'),)

class SevenTVEmote(Base):
    __tablename__ = 'seventv_emotes'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    flags = Column(Integer)
    timestamp = Column(String)
    animated = Column(Boolean, default=False)
    host_url = Column(String)

class EmoteUsage(Base):
    __tablename__ = 'emote_usage'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    emote_id = Column(String, ForeignKey('seventv_emotes.id'))
    count = Column(Integer, default=0)
    last_used = Column(DateTime, default=datetime.now)
    
    user = relationship("User", backref="emote_usage")
    emote = relationship("SevenTVEmote", backref="usage_stats")

class Nickname(Base):
    __tablename__ = 'nicknames'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    nickname = Column(String, nullable=False)
    
    user = relationship("User", backref="nicknames")

    __table_args__ = (Index('idx_nicknames_username', 'username'),)
    
class StinkHistory(Base):
    __tablename__ = 'stink_history'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    value = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    
    user = relationship("User", backref="stink_entries")

class TriviaStats(Base):
    __tablename__ = 'trivia_stats'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    correct_answers = Column(Integer, nullable=False, default=0)
    wrong_answers = Column(Integer, nullable=False, default=0)
    fastest_answers = Column(Float, nullable=True)
    games_played = Column(Integer, nullable=False, default=0)
    total_points = Column(Integer, nullable=False, default=0)
    last_played = Column(DateTime, default=datetime.now)
    
    user = relationship("User", backref="trivia_stats")

class TriviaGame(Base):
    __tablename__ = 'trivia_games'
    
    id = Column(Integer, primary_key=True)
    initiator = Column(String, ForeignKey('users.username'), nullable=False)
    category = Column(String)
    rounds = Column(Integer)
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True)
    participants = Column(JSON, default=lambda: [])
    round_results = Column(JSON, default=lambda: [])
    winner = Column(String, nullable=True)
    total_players = Column(Integer, default=0)

class TriviaRound(Base):
    __tablename__ = 'trivia_rounds'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('trivia_games.id'))
    question = Column(String)
    correct_answer = Column(String)
    options = Column(JSON)
    fastest_answer = Column(String, nullable=True)
    answer_times = Column(JSON, default=dict)
    correct_users = Column(JSON, default=list)
    wrong_users = Column(JSON, default=list)
    round_number = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)