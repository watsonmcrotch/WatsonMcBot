# WatsonMcBot

A comprehensive, AI-powered Twitch bot with Discord integration, featuring advanced channel point redeems, real-time alerts, interactive games, and stream management capabilities.

## Overview

WatsonMcBot is a sophisticated Twitch chatbot that combines conversational AI (powered by Claude), real-time event handling, multimedia generation, and extensive integration with streaming tools. The bot provides interactive entertainment, automated alerts, custom redeems, and intelligent chat responses whilst maintaining a web-based dashboard for monitoring and control.

## Core Features

### AI & Conversational Features
- **Claude AI Integration**: Natural language processing for intelligent chat responses
- **Context-Aware Responses**: Remembers user interactions, preferences, and conversation history
- **Ambient Mode**: Optionally responds to chat naturally without explicit commands
- **Custom User Information**: Track and reference custom facts about chatters
- **Sentiment Analysis**: Understands and responds to chat mood and tone
- **Nickname System**: Custom display names for users with database persistence

### Stream Alerts & Events
- **EventSub Integration**: Real-time handling of Twitch events via WebSocket
- **Follow Alerts**: Animated alerts with custom graphics and TTS
- **Subscription Alerts**: Tiered alerts for new subs, resubs, and gift subs
- **Bit Alerts**: Scaled alerts (1-10,000+) with custom videos and light effects
- **Raid Alerts**: Welcome raiders with customised animations
- **Follow Bot Detection**: Automatically detects and manages follow bot attacks

### Channel Point Redeems

#### Entertainment Redeems
- **Trivia Game Show**: Multi-round quiz game with categories, AI host commentary, and scoring
- **Fight System**: User vs bot chat battles on any topic
- **Genie Wishes**: AI-generated wish fulfilment with "monkey's paw" like outcomes
- **Priest Confessions**: Humorous AI-generated absolutions for any sin
- **Custom Songs**: AI-generated music with Suno API integration featuring simple prompt based input, or fully custom song creation guided by the chatbot
- **AI Images**: Generate custom artwork with multiple AI providers (Lumalabs as primary, fall back to OpenAI)
- **AI Videos**: Create videos using OpenAI's Sora 2 API

#### TTS & Voice Redeems
- **Multiple Voice Characters**: Watson, Dracula, Jamie, Missile, Hoya, and more
- **Custom TTS Messages**: ElevenLabs integration for high-quality voices

#### Interactive Redeems
- **Spotify Control**: Queue songs, skip tracks, pause/play
- **Light Control**: Govee smart light integration with colour changes
- **Nickname Changes**: Let viewers set their display name
- **Stink Redeem**: Humorous daily stink ratings

### Games & Interactive Features
- **Totally Not Trivial**: Full-featured quiz show with:
  - Multiple categories (Music, Movies, TV, Science, History, Art, etc...)
  - Custom AI host with personality
  - Live scoring and statistics tracking
  - Animated overlays and sound effects
  - Player history and achievements

- **Duel System**: Challenge other chatters to "edge" battles
- **Edge System**: Session-based tracking with milestones
- **Dice roll and more**: Several commands designed to provide chat with enrichment and fun

### Integrations

#### Discord
- **Dual-Bot System**: Separate Discord bot monitors and shares content and can chat to users in DM's using the same prompt as the Twitch chatbot
- **Automated Sharing**: AI-generated images, videos, and songs to designated channels

#### Spotify
- **Now Playing Widget**: Real-time song information overlay
- **Playback Control**: Commands for play, pause, skip, previous
- **Queue Management**: Add songs via channel points or commands
- **Widget Updates**: Automatic display of current track, artist, and album

#### OBS
- **WebSocket Integration**: Direct OBS control via obs-websocket
- **Scene Management**: Automated scene changes and transitions
- **Overlay System**: Dynamic text, images, and video overlays
- **Source Control**: Show/hide sources programmatically

#### External APIs
- **Claude AI**: Anthropic's Claude for conversation and content generation
- **OpenAI**: Sora 2 for video generation, GPT for images
- **ElevenLabs**: Professional text-to-speech voices
- **Suno**: AI music generation (via 3rd party service)
- **Govee**: Smart lighting control
- **7TV**: Emote tracking and statistics

## Technical Architecture

### Core Components

#### Bot System (`bot.py`)
The main bot class handles:
- Twitch connection and authentication
- Message routing and processing
- Command handling
- Event coordination
- Database interactions
- Token management

#### Services Layer
- **Database Manager** (`services/database_manager.py`): SQLAlchemy-based data persistence
- **Token Manager** (`services/twitch_token_manager.py`): OAuth token refresh and validation
- **EventSub Client** (`services/eventsub_client.py`): Twitch EventSub WebSocket connection
- **WebSocket Server** (`services/websocket_server.py`): Real-time dashboard communication
- **Flask Server** (`services/flask_server.py`): HTTP API for dashboard and integrations
- **OBS Client** (`services/obs_client.py`): OBS Studio WebSocket communication
- **Discord Monitor** (`services/discord_monitor.py`): Discord bot integration
- **Spotify Manager** (`services/spotify_manager.py`): Spotify API wrapper
- **Chat Manager** (`services/chat_manager.py`): Message parsing and emote handling

#### Database Models (`models.py`)
- Users: Profile data, statistics, conversation history
- Custom Info: User-specific facts and preferences
- Nicknames: Display name mappings
- Emote Usage: 7TV emote tracking statistics
- Trivia: Game history, rounds, and player stats
- Edge Tracking: Session data and milestones
- Game History: Word game and duel records
- Stink History: Point system tracking

#### Redeem Handlers (`redeems/`)
Each redeem has a dedicated handler class:
- `trivia_redeem.py`: Quiz game logic
- `fight_redeem.py`: Battle system
- `image_redeem.py`: AI image generation
- `video_redeem.py`: AI video creation
- `music_redeem.py`: Song generation
- And many more...

#### Alert Handlers (`alerts/`)
- `follow_alert.py`: New follower notifications
- `sub_alert.py`: Subscription handling
- `gift_alert.py`: Gift subscription events
- `bits_alert.py`: Bit cheer alerts
- `raid_alert.py`: Incoming raid handling

### Data Flow

1. **Incoming Events**
   - Twitch chat messages → TwitchIO → `event_message()`
   - EventSub notifications → WebSocket → `handle_eventsub_notification()`
   - Channel point redeems → EventSub → Specific handler

2. **Processing**
   - Message parsing and emote detection
   - User context loading from database
   - AI response generation if applicable
   - Handler-specific logic execution

3. **Output**
   - Chat responses via TwitchIO
   - Overlay events via WebSocket to companion app
   - Discord notifications via Discord.py
   - Database updates via SQLAlchemy

### Configuration

The bot uses environment variables loaded from a `.env` file. See the included `.env` file for required keys.

#### Required Environment Variables
- Twitch authentication (multiple token types)
- API keys (Claude, OpenAI, ElevenLabs, etc.)
- Discord bot token
- Spotify credentials
- Channel configuration
- Database paths

#### Configuration Files
- `config.py`: Centralised configuration loading and validation
- `.env`: Environment-specific secrets and settings
- `start.bat`: Windows startup script

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Windows OS (tested environment)
- OBS Studio with obs-websocket plugin
- Active Twitch account
- API keys for various services

### Installation Steps

1. **Clone the Repository**
```bash
git clone <repository-url>
cd WatsonMcBot
```

2. **Create Virtual Environment**
```bash
python -m venv venv
venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Environment Variables**
Create a `.env` file in the project root with all required credentials.

5. **Initialise Database**
The database will be created automatically on first run using SQLAlchemy.

6. **Configure OBS**
- Install obs-websocket v5
- Set password in `.env` as `OBS_WEBSOCKET_PASSWORD`
- Configure scenes matching the bot's expectations

7. **Set Up Discord Bot** (Optional)
- Create Discord application
- Add bot token to `.env`
- Configure channel IDs for content sharing

8. **Configure Twitch EventSub**
- Register your application at Twitch Developer Console
- Set up redirect URIs
- Generate access and refresh tokens

### Running the Bot

**Using the Startup Script (Windows)**
```batch
start.bat
```

This script:
- Activates the virtual environment
- Clears old log files
- Starts the bot via `run_bot.py`

**Manual Start**
```bash
venv\Scripts\activate
python run_bot.py
```

The bot will:
- Start Flask HTTP server on port 5555
- Start WebSocket server on port 8555
- Connect to Twitch IRC and EventSub
- Initialise Discord bot
- Connect to OBS WebSocket
- Load all handlers and services

### Dashboard Access

Once running, access the web dashboard at:
```
http://localhost:5555
```

Features:
- Real-time bot status monitoring
- Live console logs
- Chat message feed
- Stream information display
- Alert testing buttons
- Redeem triggering
- Spotify controls
- OBS scene management

## Project Structure

```
WatsonMcBot/
├── alerts/                 # Alert handler modules
│   ├── bits_alert.py
│   ├── follow_alert.py
│   ├── gift_alert.py
│   ├── raid_alert.py
│   └── sub_alert.py
├── redeems/                # Channel point redeem handlers
│   ├── crash_redeem.py
│   ├── draculatts_redeem.py
│   ├── fight_redeem.py
│   ├── genie_redeem.py
│   ├── hoya_redeem.py
│   ├── hydrate_redeem.py
│   ├── image_redeem.py
│   ├── jamie_redeem.py
│   ├── light_redeem.py
│   ├── lmao_redeem.py
│   ├── missiletts_redeem.py
│   ├── music_redeem.py
│   ├── newsreel_redeem.py
│   ├── nickname_redeem.py
│   ├── priest_redeem.py
│   ├── spotify_queue_redeem.py
│   ├── spud_redeem.py
│   ├── stinky_redeem.py
│   ├── stories_redeem.py
│   ├── trivia_redeem.py
│   ├── video_redeem.py
│   └── watsontts_redeem.py
├── services/               # Core service modules
│   ├── chat_manager.py
│   ├── database_manager.py
│   ├── dashboard_broadcaster.py
│   ├── discord_monitor.py
│   ├── eventsub_client.py
│   ├── flask_server.py
│   ├── obs_client.py
│   ├── spotify_manager.py
│   ├── spotify_widget_handler.py
│   ├── state_manager.py
│   ├── tts_queue.py
│   ├── twitch_token_manager.py
│   └── websocket_server.py
├── templates/              # HTML templates for dashboard
│   └── dashboard.html
├── logs/                   # Log files (auto-generated)
├── sounds/                 # Audio files for redeems
├── data/                   # JSON data storage
├── bot.py                  # Main bot class
├── config.py               # Configuration management
├── models.py               # Database models
├── run_bot.py              # Entry point
├── start.bat               # Windows startup script
├── govee_devices.py        # Govee light API wrapper
├── .env                    # Environment variables (not in repo)
└── requirements.txt        # Python dependencies
```

## Commands

### Chat Commands

#### User Commands
- `!commands` - Display available commands
- `!points` - Check channel point balance
- `!stats` - View personal statistics
- `!emotes [username]` - View emote usage statistics
- `!trivia` - Check trivia statistics
- `!edge` - View edge tracking status
- `!stink` - Check stink points

#### Moderator Commands
- `!setinfo <username> <key> <value>` - Store custom user information
- `!deleteinfo <username> <key>` - Remove custom user information
- `!getinfo <username>` - Retrieve all custom user information
- `!setnickname <username> <nickname>` - Set user's display nickname
- `!removenickname <username>` - Remove user's nickname
- `!addspam <pattern>` - Add spam detection pattern
- `!removespam <pattern>` - Remove spam detection pattern

#### Streamer Commands
- `!listrewards` - List all channel point rewards with IDs
- `!testattack <amount>` - Test follow bot detection
- `!testcheer <bits> [user] [message]` - Test bit alert
- `!testfollow <username>` - Test follow alert
- `!testgift <recipient/amount>` - Test gift subscription alert
- `!emotestate` - Check emote tracker status

### Dashboard Controls

Available via the web interface:
- Test all alert types
- Trigger channel point redeems
- Control Spotify playback
- Manage OBS scenes
- Execute bot commands
- Clear statistics
- Monitor real-time logs and chat

## Advanced Features

### Ambient Mode

When enabled, the bot can naturally participate in chat without explicit commands:
- Monitors chat context and flow
- Responds based on configurable thresholds
- Maintains conversation history
- Respects cooldown periods

Configuration in `.env`:
```
ENABLE_AMBIENT_MODE=True
AMBIENT_RESPONSE_THRESHOLD=60
AMBIENT_MIN_INTERVAL=60
AMBIENT_MAX_PER_HOUR=30
AMBIENT_CHAT_BUFFER_SIZE=100
```

### Edge Tracking System

A specialised feature for tracking user sessions:
- Session-based streak tracking
- Milestone celebrations (5, 10, 15, 30 edges)
- Historical statistics
- Database persistence across streams

### Follow Bot Protection

Automatic detection and response system:
- Monitors follow rate and patterns
- Identifies coordinated bot attacks
- Temporarily disables follow alerts during attacks
- Queues legitimate follows for later processing
- Sends moderation notifications

### Smart Lighting Integration

Govee API integration for stream lighting:
- Scene-based colour changes
- Alert-triggered effects
- Bit amount scaling (different colours for 100+ and 1000+)
- API rate limiting and error handling

### TTS Queue System

Manages multiple TTS requests efficiently:
- Asynchronous audio processing
- Queue-based playback
- Prevents audio overlap
- Handles multiple voice providers
- Automatic cleanup of temporary files

## Trivia Game Show Details

The **Totally Not Trivial** system is one of the most complex features:

### Game Flow
1. **Redeem Activation**: User redeems "Totally Not Trivial"
2. **Setup Phase**: 60-second window to choose category and rounds
3. **Game Introduction**: AI-generated host announcement with music
4. **Question Rounds**: 
   - Question display with 4 options
   - 30-second answer window
   - Fastest correct answer wins points
   - AI host commentary between rounds
5. **Game Conclusion**: Final scores, winner announcement, statistics update

### Categories
- **Music**: Songs, artists, albums, music history
- **Movies**: Films, actors, directors, cinema trivia
- **TV**: Television shows, series, characters
- **Science**: Scientific concepts, discoveries, facts
- **History**: Historical events, figures, dates
- **Art**: Artists, movements, famous works

### Scoring System
- Correct answer: +10 points
- Fastest correct: +5 bonus
- Statistics tracked across all games
- Leaderboards maintained in database

### AI Host Personality
The AI host (Claude-powered) provides:
- Witty commentary between rounds
- Reactions to player performance
- References to player history
- Dynamic responses based on game state
- Character limit enforcement for natural pacing

## Database Schema

### Core Tables

**Users**
- username (primary key)
- messages_count
- first_seen, last_seen
- conversation_history (JSON)
- favorite_emotes (JSON)
- sentiment_history (JSON)
- topics_discussed (JSON)
- active_times (JSON)
- responded_to_count
- questions_asked

**CustomInfo**
- username (foreign key)
- info_type
- value

**Nicknames**
- username (foreign key)
- nickname

**EmoteUsage**
- username (foreign key)
- emote_id (foreign key)
- count
- last_used

**TriviaStats**
- username (foreign key)
- games_played
- correct_answers
- wrong_answers
- fastest_answers
- total_points

**EdgeStreak**
- username (primary key)
- current_streak
- session_start
- last_edge_time

**StinkHistory**
- username (foreign key)
- value
- timestamp

## API Integration Details

### Claude AI (Anthropic)
- Model: claude-sonnet-4-5-20250929
- Used for: Chat responses, game commentary, content generation
- Temperature: Variable (0.7-0.8 for creativity)
- Context: User history, stream info, custom facts

### OpenAI
- Sora 2: Video generation (12-second clips, 1280x720)
- DALL-E 3: Image generation (fallback option)
- Rate limiting and error handling implemented

### ElevenLabs
- Multiple voice IDs for different characters
- Output format: MP3 44.1kHz 128kbps
- Model: eleven_multilingual_v2
- Async generation with queue system

### Suno API
- AI music generation from text prompts
- Custom song creation with topics and styles
- Automatic artwork generation
- Discord sharing integration

### Govee API
- Smart light control
- Colour RGB setting
- Device management
- Rate limiting compliance

## Troubleshooting

### Common Issues

**Bot Won't Connect**
- Verify all tokens in `.env` are valid
- Check Twitch API credentials
- Ensure channel name matches exactly
- Review logs in `logs/bot.log`

**EventSub Not Receiving Events**
- Confirm broadcaster token is valid
- Check subscription status in logs
- Verify webhooks are properly registered
- Test with mock events using test commands

**Database Errors**
- Ensure write permissions in project directory
- Check SQLAlchemy logs for specific errors
- Verify database file isn't locked
- Consider database backup and recreation

**Audio Issues**
- Confirm sound files exist in `sounds/` directory
- Check file permissions
- Verify audio file formats (MP3 recommended)
- Review TTS queue status

**OBS Connection Failed**
- Verify obs-websocket is installed
- Check WebSocket port (default 4455)
- Confirm password matches `.env`
- Ensure OBS is running

### Debug Mode

Enable detailed logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Log Files
- `logs/bot.log` - Main bot operations
- `logs/server.log` - Flask server activity
- `logs/combined.log` - Aggregated logs

## Development & Extension

### Adding New Redeems

1. **Create Handler Class**
```python
class NewRedeem:
    def __init__(self, db_manager, send_companion_event):
        self.db_manager = db_manager
        self.send_companion_event = send_companion_event
    
    async def process_redeem(self, channel, username, input_text):
        # Your logic here
        pass
```

2. **Register in bot.py**
```python
self.new_redeem = NewRedeem(self.db_manager, self.send_companion_event)
```

3. **Add to EventSub Handler**
```python
elif reward_title == 'New Redeem':
    await self.new_redeem.process_redeem(channel, username, user_input)
```

### Adding New Commands

```python
@commands.command(name='newcommand')
async def new_command(self, ctx):
    # Command logic
    await ctx.send("Response")
```

### Adding Database Models

```python
class NewModel(Base):
    __tablename__ = 'new_table'
    
    id = Column(Integer, primary_key=True)
    # Additional columns
```

## Performance Considerations

### Resource Management
- Async/await used throughout for non-blocking operations
- Database sessions properly closed after use
- WebSocket connections monitored and reconnected
- Audio playback uses separate threads
- API rate limiting respected

### Caching
- Emote data cached in memory
- User contexts loaded once per interaction
- Token refresh only when needed
- Spotify state updates at intervals

### Scaling
- Single-threaded async design
- Database connection pooling available
- WebSocket message batching
- Queue systems for TTS and audio

## Security Notes

- All sensitive credentials in `.env` (not committed)
- Token refresh automation
- Input sanitisation for user-provided content
- Spam detection and bot protection
- Rate limiting on external APIs
- Secure WebSocket connections available

## Credits & Acknowledgements

### APIs & Services
- Anthropic (Claude AI)
- OpenAI (Sora, DALL-E)
- ElevenLabs (Text-to-Speech)
- Suno (Music Generation)
- Twitch (Platform & APIs)
- Discord (Bot Integration)
- Spotify (Music Integration)
- Govee (Smart Lighting)
- 7TV (Emote Platform)

### Libraries & Frameworks
- TwitchIO: Twitch bot framework
- Discord.py: Discord integration
- Flask: Web server
- SQLAlchemy: Database ORM
- Anthropic Python SDK
- Spotipy: Spotify API wrapper
- obs-websocket-py: OBS control
- aiohttp: Async HTTP client

## Licence

This project is for personal/educational use. Ensure you comply with all third-party API terms of service when deploying.

## Support & Contact

For issues, questions, or contributions, please refer to the project repository.

---

**Version**: 2.0
**Last Updated**: October 2025
**Python Version**: 3.10+
**Platform**: Windows (Primary), Linux (Experimental)
