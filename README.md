# WatsonMcBot

A comprehensive, AI-powered Twitch bot with Discord integration, featuring advanced channel point redeems, real-time alerts, interactive games, and stream management capabilities.

## Overview

WatsonMcBot is a sophisticated Twitch chatbot that combines conversational AI, real-time event handling, multimedia generation, and extensive integration with streaming tools. The bot provides interactive entertainment, automated alerts, custom redeems, and intelligent chat responses whilst maintaining a web-based dashboard for monitoring and control.

## Core Features

### AI & Conversational Features
- **AI Integration**: Natural language processing for intelligent chat responses
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

- **Edge System**: Session-based streak tracking with milestones (PB, 69, 100, every 50), recovery cooldowns, blessings, and bust mechanics
- **Duel System**: Challenge other chatters to edge battles
- **Dice Rolls**: Configurable dice rolling with spam protection
- **Rizz**: Fun social command with sound effects and random messages

### Integrations

#### Discord
- **Dual-Bot System**: Separate Discord bot monitors and shares content and can chat to users in DM's using the same prompt as the Twitch chatbot
- **Automated Sharing**: AI-generated images, videos, and songs to designated channels

#### Spotify
- **Now Playing Widget**: Real-time song information overlay
- **Playback Control**: Commands for skip and now-playing
- **Queue Management**: Add songs via channel points
- **Widget Updates**: Automatic display of current track, artist, and album

#### OBS
- **WebSocket Integration**: Direct OBS control via obsws-python
- **Scene Management**: Automated scene changes with companion reactions
- **Overlay System**: Dynamic text, images, and video overlays
- **Source Control**: Show/hide sources programmatically

#### External APIs
- **Anthropic**: AI for conversation and content generation
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
- Event coordination
- Database interactions
- Token management
- Shared HTTP session and API clients

#### Command Cogs (`cogs/`)
Commands are organised into twitchio Cogs for modularity:
- **FunCog**: General commands (`!commands`, `!list`, `!dadjoke`, `!discord`)
- **StreamCog**: Stream interaction (`!emotes`, `!topemotes`, `!song`, `!skip`, `!roll`, `!rizz`, `!translate`, `!replay`, `!stinky`, `!nickname`, `!setprompt`, `!removeprompt`, `!viewprompt`)
- **EdgeCog**: Edge game system (`!edge`, `!edgestats`, `!edgetop`, `!duel`)
- **TriviaCog**: Trivia display (`!triviastats`, `!lastgame`, `!leaderboard`)
- **AdminCog**: Admin/streamer commands (`!addinfo`, `!deleteinfo`, `!getinfo`, `!addspam`, `!removespam`, `!listspam`, `!reloademotes`, `!listrewards`, stat clearing)
- **AdminTestCog**: Testing commands (`!ping`, `!testfollow`, `!testcheer`, `!testsub`, `!testraid`, `!testgift`, `!testimage`, `!testvideo`, `!testsong`, etc.)
- **OverlayCog**: WatsonOS overlay mod commands (`!effect`, `!errors`, `!tbc`, `!maze`, `!clippy`, `!desktop`)
- **CompanionCog**: Companion interaction (`!pet`, `!feed`, `!slap`, `!kiss`)

#### Services Layer
- **Database Manager** (`services/database_manager.py`): SQLAlchemy-based data persistence
- **Token Manager** (`services/twitch_token_manager.py`): OAuth token refresh and validation
- **EventSub Client** (`services/eventsub_client.py`): Twitch EventSub WebSocket connection
- **WebSocket Server** (`services/websocket_server.py`): Real-time dashboard communication
- **Flask Server** (`services/flask_server.py`): HTTP API for dashboard and integrations
- **OBS Client** (`services/obs_client.py`): OBS Studio WebSocket communication via obsws-python
- **Chat Manager** (`services/chat_manager.py`): Message parsing and emote handling
- **TTS Queue** (`services/tts_queue.py`): Async audio playback queue
- **State Manager** (`services/state_manager.py`): Bot state tracking
- **Dashboard Broadcaster** (`services/dashboard_broadcaster.py`): Real-time dashboard updates
- **Spotify Widget Handler** (`services/spotify_widget_handler.py`): Spotify overlay updates

#### Database Models (`models.py`)
- Users: Profile data, statistics, conversation history
- Custom Info: User-specific facts and preferences
- Nicknames: Display name mappings
- Trivia: Game history, rounds, and player stats
- Edge Tracking: Session data, streaks, and milestones
- Stink History: Stink rating tracking

#### Redeem Handlers (`redeems/`)
Each redeem has a dedicated handler class:
- `trivia_redeem.py`: Quiz game logic
- `fight_redeem.py`: Battle system
- `image_redeem.py`: AI image generation
- `video_redeem.py`: AI video creation
- `music_redeem.py`: Song generation
- `light_redeem.py`: Govee smart light control
- `stinky_redeem.py`: Stink rating system
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

The bot uses environment variables loaded from a `.env` file.

#### Required Environment Variables
- Twitch authentication (multiple token types)
- API keys (Anthropic, OpenAI, ElevenLabs, etc.)
- Discord bot token
- Spotify credentials
- Channel configuration
- Database paths

#### Configuration Files
- `config.py`: Centralised configuration loading with `BASE_DIR` for portable path resolution
- `.env`: Environment-specific secrets and settings
- `start.bat`: Windows startup script

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Windows OS (tested environment)
- OBS Studio with obs-websocket v5
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
- Load all command Cogs and handlers

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
├── cogs/                   # Command modules (twitchio Cogs)
│   ├── __init__.py
│   ├── admin_cog.py
│   ├── admin_test_cog.py
│   ├── companion_cog.py
│   ├── edge_cog.py
│   ├── fun_cog.py
│   ├── overlay_cog.py
│   ├── stream_cog.py
│   └── trivia_cog.py
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
│   ├── dashboard_broadcaster.py
│   ├── database_manager.py
│   ├── eventsub_client.py
│   ├── flask_server.py
│   ├── obs_client.py
│   ├── spotify_widget_handler.py
│   ├── state_manager.py
│   ├── tts_queue.py
│   ├── twitch_token_manager.py
│   └── websocket_server.py
├── overlays/               # Browser source overlays for OBS
│   ├── assets/             # Fonts, images, videos, gifs
│   ├── chat_overlay_main.html
│   ├── chat_overlay_misc.html
│   ├── companion.html
│   ├── fullscreen_overlay.html
│   └── spotify_widget.html
├── templates/              # HTML templates for dashboard
│   └── dashboard.html
├── sounds/                 # Audio files for alerts and redeems
├── data/                   # JSON data storage and misc assets
├── bot.py                  # Main bot class
├── config.py               # Configuration management
├── models.py               # Database models (SQLAlchemy)
├── govee_devices.py        # Govee light API wrapper
├── run_bot.py              # Entry point
├── start.bat               # Windows startup script
├── .env                    # Environment variables (not in repo)
└── requirements.txt        # Python dependencies
```

## Commands

### User Commands
| Command | Aliases | Description |
|---------|---------|-------------|
| `!commands` | `!cmds`, `!menu` | Display available commands |
| `!dadjoke` | | Fetch a random dad joke |
| `!discord` | | Get Discord invite (followers only) |
| `!edge` | `!edge1`-`!edge10` | Edge streak game (1-10 attempts) |
| `!edgestats` | | View edge statistics for a user |
| `!edgetop` | `!edgelords`, `!topedge` | Edge leaderboard |
| `!duel` | | Challenge someone to an edge-off |
| `!emotes` | `!emote` | View emote usage stats |
| `!topemotes` | | Channel-wide emote leaderboard |
| `!nickname` | | View a user's nickname |
| `!stinky` | `!stink`, `!smelly` | View stink report |
| `!song` | | Currently playing Spotify track |
| `!roll` | | Roll dice (e.g. `!roll 2d6`) |
| `!rizz` | | Shoot your shot at someone |
| `!translate` | | Translate text to another language |
| `!triviastats` | | View trivia statistics |
| `!lastgame` | | Summary of last trivia game |
| `!leaderboard` | `!triviatop` | Trivia leaderboard |
| `!pet` | | Pet the companion |
| `!feed` | | Feed the companion |
| `!slap` | | Slap the companion |
| `!kiss` | | Kiss the companion |

### Moderator Commands
| Command | Description |
|---------|-------------|
| `!skip` | Skip current Spotify track |
| `!replay` | Replay the last video |
| `!reloademotes` | Reload 7TV emotes |
| `!addspam <pattern>` | Add spam detection pattern |
| `!removespam <pattern>` | Remove spam detection pattern |
| `!listspam` | View spam patterns |
| `!effect`, `!errors`, `!tbc`, `!maze`, `!clippy`, `!desktop` | WatsonOS overlay commands |

### Streamer Commands
| Command | Description |
|---------|-------------|
| `!list` | List all admin commands |
| `!addinfo <user> <attr> <value>` | Store custom user info |
| `!deleteinfo <user> <attr>` | Remove specific user info |
| `!deletealluserinfo <user>` | Remove all user info |
| `!getinfo <user>` | View all custom info for a user |
| `!setprompt <user> <prompt>` | Set custom AI prompt for user |
| `!removeprompt <user>` | Remove custom AI prompt |
| `!viewprompt <user>` | View custom AI prompt |
| `!listrewards` | List channel point reward IDs |
| `!clearalledgestats` | Clear all edge statistics |
| `!clearedgestats <user>` | Clear edge stats for one user |
| `!clearalltriviastats` | Clear all trivia statistics |
| `!cleartriviastats <user>` | Clear trivia stats for one user |

### Test Commands (Mods)
| Command | Description |
|---------|-------------|
| `!ping` | Bot connectivity check |
| `!emotestate` | Emote tracker debug info |
| `!tokencheck` | Validate bot/broadcaster tokens |
| `!testfollow <user>` | Simulate follow alert |
| `!testcheer [bits] [user]` | Simulate bit alert |
| `!testsub` | Simulate subscription |
| `!testresub` | Simulate resubscription |
| `!testgift <user/amount>` | Simulate gift sub |
| `!testmassgift [amount]` | Simulate mass gift |
| `!testraid <user> [viewers]` | Simulate raid |
| `!testimage [prompt]` | Test AI image generation |
| `!testvideo [prompt]` | Test AI video generation |
| `!testsong [prompt]` | Test AI song generation |
| `!testattack [amount]` | Test follow bot detection |

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

A session-based streak game with depth:
- Streak tracking with escalating bust probability
- Milestone celebrations (personal best, 69, 100, every 50)
- Recovery cooldowns after busting (proportional to streak)
- Blessing system (2% chance — no recovery for 15 minutes)
- Duel mode for head-to-head edge battles
- Sound effects for busts, milestones, and blessings
- Persistent statistics across streams

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
- highest_streak
- total_edges
- total_busts
- last_streak
- longest_session
- session_start

**StinkHistory**
- username (foreign key)
- value
- timestamp

## API Integration Details

### Anthropic
- Used for: Chat responses, game commentary, content generation, translations
- Temperature: Variable (0.7-0.8 for creativity)
- Context: User history, stream info, custom facts
- Shared client instance across all handlers

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
- Verify obs-websocket v5 is installed
- Check WebSocket port (default 4455)
- Confirm password matches `.env`
- Ensure OBS is running

### Log Files
- `logs/bot.log` - Main bot operations
- `logs/server.log` - Flask server activity
- `logs/combined.log` - Aggregated logs

## Development & Extension

### Adding New Commands

Create a new Cog in the `cogs/` directory:

```python
from twitchio.ext import commands

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='mycommand')
    async def my_command(self, ctx):
        await ctx.send("Hello!")

def prepare(bot):
    bot.add_cog(MyCog(bot))
```

The Cog will be loaded automatically if added to the `cog_modules` list in `bot.py`'s `event_ready`.

### Adding New Redeems

1. **Create Handler Class** in `redeems/`
2. **Register in `bot.py`** during initialisation
3. **Add to EventSub Handler** in the channel points redemption section

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
- Shared aiohttp session for all HTTP requests
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
- Anthropic (AI)
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
- obsws-python: OBS WebSocket control
- aiohttp: Async HTTP client
- Spotipy: Spotify API wrapper

## Licence

This project is for personal/educational use. Ensure you comply with all third-party API terms of service when deploying.

## Support & Contact

For issues, questions, or contributions, please refer to the project repository.

---

**Version**: 3.0
**Last Updated**: April 2026
**Python Version**: 3.10+
**Platform**: Windows (Primary)
