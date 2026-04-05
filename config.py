import os
from pathlib import Path
from dotenv import load_dotenv
import logging

load_dotenv()

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
SOUNDS_DIR = BASE_DIR / 'sounds'
SCRIPTS_DIR = Path(os.getenv('SCRIPTS_DIR', str(BASE_DIR / 'data')))

LOGS_DIR = BASE_DIR / 'logs'
TEMPLATES_DIR = BASE_DIR / 'templates'
DATA_DIR = SCRIPTS_DIR / 'data'

for directory in [LOGS_DIR, TEMPLATES_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / 'bot.log'
SERVER_LOG = LOGS_DIR / 'server.log'
COMBINED_LOG = LOGS_DIR / 'combined.log'
USER_PROFILES_PATH = SCRIPTS_DIR / 'user_profiles.json'
CUSTOM_INFO_PATH = SCRIPTS_DIR / 'custom_info.json'
STINK_HISTORY_PATH = SCRIPTS_DIR / 'stink_history.json'
NICKNAMES_PATH = SCRIPTS_DIR / 'nicknames.json'
EMOTE_DATA_PATH = os.getenv('EMOTE_DATA_PATH')

FLASK_HOST = '127.0.0.1'
FLASK_PORT = int(os.getenv('FLASK_PORT', 5555))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

WEBSOCKET_HOST = '127.0.0.1'
WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', 8555))

BOT_NAME = 'watsonmcbot'
STREAMER_NAME = 'watsonmcrotch'
CHANNEL_NAME = 'watsonmcrotch'

SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'Watson')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

TWITCH_CLIENT_ID = os.getenv('CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('CLIENT_SECRET')
BROADCASTER_CLIENT_ID = os.getenv('BROADCASTER_CLIENT_ID')
BROADCASTER_CLIENT_SECRET = os.getenv('BROADCASTER_SECRET')
BOT_ACCESS_TOKEN = os.getenv('BOT_ACCESS_TOKEN')
BOT_REFRESH_TOKEN = os.getenv('BOT_REFRESH_TOKEN')
TWITCH_READ_TOKEN = os.getenv('TWITCH_READ_TOKEN')
TWITCH_READ_REFRESH_TOKEN = os.getenv('TWITCH_READ_REFRESH_TOKEN')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = f'http://{FLASK_HOST}:{FLASK_PORT}/discord/callback'
DISCORD_CHANNEL_IMAGES = os.getenv('DISCORD_CHANNEL_IMAGES')
DISCORD_CHANNEL_VIDEOS = os.getenv('DISCORD_CHANNEL_VIDEOS')
DISCORD_CHANNEL_MUSIC = os.getenv('DISCORD_CHANNEL_MUSIC')

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

RESPONSE_COOLDOWN = int(os.getenv('RESPONSE_COOLDOWN', 10))
REMINDER_COOLDOWN = int(os.getenv('REMINDER_COOLDOWN', 1800))

# WatsonOS Overlay Settings
OVERLAY_BASE_URL = os.getenv('OVERLAY_BASE_URL', f'http://{FLASK_HOST}:{FLASK_PORT}/stream')

# Ambient Conversational Mode Settings
ENABLE_AMBIENT_MODE = os.getenv('ENABLE_AMBIENT_MODE', 'True').lower() == 'true'
AMBIENT_RESPONSE_THRESHOLD = int(os.getenv('AMBIENT_RESPONSE_THRESHOLD', 60))
AMBIENT_MIN_INTERVAL = int(os.getenv('AMBIENT_MIN_INTERVAL', 60))
AMBIENT_MAX_PER_HOUR = int(os.getenv('AMBIENT_MAX_PER_HOUR', 30))
AMBIENT_CHAT_BUFFER_SIZE = int(os.getenv('AMBIENT_CHAT_BUFFER_SIZE', 100))

def verify_config():
    critical_vars = [
        'BOT_NAME',
        'STREAMER_NAME',
        'CHANNEL_NAME',
        'TWITCH_CLIENT_ID',
        'TWITCH_CLIENT_SECRET',
        'BOT_ACCESS_TOKEN',
        'BOT_REFRESH_TOKEN',
        'TWITCH_READ_TOKEN',
        'TWITCH_READ_REFRESH_TOKEN',
        'CLAUDE_API_KEY',
        'ADMIN_PASSWORD'
    ]
    
    optional_vars = [
        'DISCORD_TOKEN',
        'SPOTIFY_CLIENT_ID',
        'SPOTIFY_CLIENT_SECRET'
    ]
    
    missing_critical = [var for var in critical_vars if not globals().get(var)]
    if missing_critical:
        raise ValueError(f"Missing required configuration variables: {', '.join(missing_critical)}")
    
    missing_optional = [var for var in optional_vars if not globals().get(var)]
    if missing_optional:
        logging.warning(f"Missing optional configuration variables: {', '.join(missing_optional)}")

try:
    verify_config()
except ValueError as e:
    logging.critical(f"Configuration Error: {e}")
    raise

__all__ = [
    'BASE_DIR', 'SOUNDS_DIR', 'SCRIPTS_DIR', 'LOGS_DIR', 'TEMPLATES_DIR', 'DATA_DIR',
    'LOG_FILE', 'SERVER_LOG', 'COMBINED_LOG', 'EMOTE_DATA_PATH',
    'USER_PROFILES_PATH', 'CUSTOM_INFO_PATH', 'STINK_HISTORY_PATH',
    'NICKNAMES_PATH', 'FLASK_HOST', 'FLASK_PORT', 'FLASK_DEBUG',
    'WEBSOCKET_HOST', 'WEBSOCKET_PORT', 'BOT_NAME', 'STREAMER_NAME',
    'CHANNEL_NAME', 'SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD',
    'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET', 'BOT_ACCESS_TOKEN',
    'BOT_REFRESH_TOKEN',
    'TWITCH_READ_TOKEN',
    'TWITCH_READ_REFRESH_TOKEN',
    'CLAUDE_API_KEY', 'DISCORD_TOKEN', 'DISCORD_CLIENT_ID',
    'DISCORD_CLIENT_SECRET', 'DISCORD_REDIRECT_URI', 'DISCORD_CHANNEL_IMAGES',
    'DISCORD_CHANNEL_VIDEOS', 'DISCORD_CHANNEL_MUSIC', 'SPOTIFY_CLIENT_ID',
    'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI', 'RESPONSE_COOLDOWN',
    'REMINDER_COOLDOWN', 'ENABLE_AMBIENT_MODE', 'AMBIENT_RESPONSE_THRESHOLD',
    'AMBIENT_MIN_INTERVAL', 'AMBIENT_MAX_PER_HOUR', 'AMBIENT_CHAT_BUFFER_SIZE',
    'BROADCASTER_CLIENT_ID', 'BROADCASTER_CLIENT_SECRET',
    'OVERLAY_BASE_URL'
]