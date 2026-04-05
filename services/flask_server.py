from flask import Flask, send_from_directory, request, Response, render_template, jsonify
from functools import wraps
import asyncio
import logging
from pathlib import Path
import os
import sys
from config import BASE_DIR

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
logging.basicConfig(level=logging.INFO)

# API key for authenticating dashboard/API requests
DASHBOARD_API_KEY = os.getenv('DASHBOARD_API_KEY')
if not DASHBOARD_API_KEY:
    logging.warning("DASHBOARD_API_KEY not set — all /api/ endpoints will reject requests. Set this env var to enable the dashboard.")

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not DASHBOARD_API_KEY:
            return jsonify({'error': 'API key not configured on server'}), 503
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if key != DASHBOARD_API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# Global bot reference (will be set when bot starts)
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

def run_async(coro, timeout=30):
    """Run an async coroutine on the bot's event loop from Flask threads.
    Returns the coroutine's result or raises on timeout/error."""
    import asyncio
    future = asyncio.run_coroutine_threadsafe(coro, bot_instance.loop)
    return future.result(timeout=timeout)

STREAM_OVERLAY_DIR = os.getenv('STREAM_OVERLAY_DIR', r'C:\2026 Stream\Website\stream')
OVERLAYS_DIR = str(BASE_DIR / 'overlays')

@app.route('/stream/<path:filename>')
def serve_stream_overlay(filename):
    """Serve WatsonOS stream overlay HTML files for OBS browser sources."""
    return send_from_directory(STREAM_OVERLAY_DIR, filename)

@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

@app.route('/<path:filename>')
def serve_overlay_file(filename):
    """Serve overlay HTML files and assets (CSS/JS/sounds) from the overlays directory."""
    return send_from_directory(OVERLAYS_DIR, filename)

@app.route('/')
def dashboard():
    """Serve the main dashboard"""
    return render_template('dashboard.html', api_key=DASHBOARD_API_KEY or '')

@app.route('/api/status')
@require_api_key
def api_status():
    """Get current bot status"""
    try:
        if not bot_instance:
            return jsonify({
                'statuses': {
                    'twitch': False,
                    'discord': False,
                    'eventsub': False,
                    'database': False
                },
                'stream_info': {},
                'now_playing': {},
                'active_systems': {}
            })

        # Get status from bot - check if bot is connected
        twitch_ready = False
        if hasattr(bot_instance, 'is_ready'):
            # is_ready is a method that needs to be called
            try:
                twitch_ready = bot_instance.is_ready()
            except Exception:
                # If it's not a method, try as property
                twitch_ready = bot_instance.is_ready if not callable(bot_instance.is_ready) else False

        discord_ready = False
        if hasattr(bot_instance, 'discord_bot') and bot_instance.discord_bot:
            discord_ready = bot_instance.discord_bot.is_ready()

        statuses = {
            'twitch': twitch_ready,
            'discord': discord_ready,
            'eventsub': True,  # If bot is running, eventsub is running
            'database': hasattr(bot_instance, 'db_manager') and bot_instance.db_manager is not None
        }

        # Get stream info
        stream_info = {
            'is_live': bot_instance.is_live if hasattr(bot_instance, 'is_live') else False,
            'viewers': bot_instance.viewer_count if hasattr(bot_instance, 'viewer_count') else 0,
            'uptime': str(bot_instance.stream_uptime) if hasattr(bot_instance, 'stream_uptime') and bot_instance.stream_uptime else 'N/A',
            'game': bot_instance.stream_category if hasattr(bot_instance, 'stream_category') else 'N/A',
            'title': bot_instance.stream_title if hasattr(bot_instance, 'stream_title') else 'N/A'
        }

        # Get now playing
        now_playing = {}
        if hasattr(bot_instance, 'current_song') and bot_instance.current_song:
            now_playing = {
                'song': bot_instance.current_song.get('name', 'Unknown'),
                'artist': bot_instance.current_song.get('artist', 'Unknown'),
                'album': bot_instance.current_song.get('album', '')
            }

        # Get active systems
        active_systems = {
            'trivia': len(bot_instance.trivia_games) if hasattr(bot_instance, 'trivia_games') else 0,
            'edge': len(bot_instance.edge_game_manager.active_streaks) if hasattr(bot_instance, 'edge_game_manager') else 0,
            'duels': len(bot_instance.active_duels) if hasattr(bot_instance, 'active_duels') else 0,
            'fights': len(bot_instance.active_fights) if hasattr(bot_instance, 'active_fights') else 0,
            'ambient_mode': bot_instance.ambient_mode_enabled if hasattr(bot_instance, 'ambient_mode_enabled') else False
        }

        return jsonify({
            'statuses': statuses,
            'stream_info': stream_info,
            'now_playing': now_playing,
            'active_systems': active_systems
        })
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/logs')
@require_api_key
def api_logs():
    """Get recent logs"""
    try:
        log_file = Path(__file__).parent.parent / 'logs' / 'bot.log'
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent = lines[-100:]
                return jsonify({'logs': [{'message': line.strip()} for line in recent]})
        return jsonify({'logs': []})
    except Exception as e:
        logging.error(f"Error reading logs: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/test/<alert_type>', methods=['POST'])
@require_api_key
def api_test_alert(alert_type):
    """Trigger test alerts"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        import asyncio

        async def run_alert():
            if alert_type == 'follow':
                if hasattr(bot_instance, 'follow_alert'):
                    await bot_instance.follow_alert.trigger('TestUser')
                else:
                    return False, 'Follow alert not available'
            elif alert_type == 'sub':
                if hasattr(bot_instance, 'sub_alert'):
                    mock_data = {
                        'user_id': '12345',
                        'user_login': 'testuser',
                        'user_name': 'TestUser',
                        'tier': '1000',
                        'is_gift': False
                    }
                    await bot_instance.sub_alert.trigger('TestUser', mock_data)
                else:
                    return False, 'Sub alert not available'
            elif alert_type == 'raid':
                if hasattr(bot_instance, 'raid_alert'):
                    await bot_instance.raid_alert.trigger('TestRaider', 50)
                else:
                    return False, 'Raid alert not available'
            elif alert_type == 'bits':
                if hasattr(bot_instance, 'bit_alert'):
                    await bot_instance.bit_alert.trigger('TestUser', 100, 'Test cheer!')
                else:
                    return False, 'Bit alert not available'
            elif alert_type == 'gift':
                if hasattr(bot_instance, 'gift_alert'):
                    await bot_instance.gift_alert.trigger('TestGifter', 5, None)
                else:
                    return False, 'Gift alert not available'
            elif alert_type == 'image':
                channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
                if channel and hasattr(bot_instance, 'image_redeem'):
                    await bot_instance.image_redeem.process_image_redeem(channel, 'TestUser', 'https://via.placeholder.com/800x600')
                else:
                    return False, 'Image redeem not available'
            elif alert_type == 'video':
                channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
                if channel and hasattr(bot_instance, 'video_redeem'):
                    await bot_instance.video_redeem.process_video_redeem(channel, 'TestUser', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
                else:
                    return False, 'Video redeem not available'
            elif alert_type == 'song':
                channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
                if channel and hasattr(bot_instance, 'song_redeem'):
                    await bot_instance.song_redeem.process_song_redeem(channel, 'TestUser', 'https://open.spotify.com/track/test')
                else:
                    return False, 'Song redeem not available'
            else:
                return False, 'Unknown alert type'

            return True, None

        success, error = run_async(run_alert())
        if not success:
            return jsonify({'error': error}), 503
        return jsonify({'message': f'{alert_type} alert triggered successfully'})
    except Exception as e:
        logging.error(f"Error triggering test alert: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/redeem/<redeem_type>', methods=['POST'])
@require_api_key
def api_test_redeem(redeem_type):
    """Trigger test redeems"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        import asyncio

        async def run_redeem():
            if redeem_type == 'stinky':
                if hasattr(bot_instance, 'stinky_redeem'):
                    await bot_instance.stinky_redeem.process_stinky_redeem(channel, 'TestUser', '#FF0000')
                else:
                    return False, 'Stinky redeem not available'
            elif redeem_type == 'nickname':
                if hasattr(bot_instance, 'nickname_redeem'):
                    await bot_instance.nickname_redeem.process_nickname_change(channel, 'TestUser', 'TestNick')
                else:
                    return False, 'Nickname redeem not available'
            elif redeem_type == 'trivia':
                if hasattr(bot_instance, 'trivia_game'):
                    await bot_instance.trivia_game.process_trivia_redeem(channel, 'TestUser')
                else:
                    return False, 'Trivia redeem not available'
            elif redeem_type == 'lmao':
                if hasattr(bot_instance, 'lmao_redeem'):
                    await bot_instance.lmao_redeem.process_lmao_redeem(channel)
                    # Give time for background tasks to complete
                    await asyncio.sleep(0.5)
                else:
                    return False, 'LMAO redeem not available'
            elif redeem_type == 'jamie':
                if hasattr(bot_instance, 'jamie_redeem'):
                    await bot_instance.jamie_redeem.process_jamie_redeem(channel)
                    await asyncio.sleep(0.5)
                else:
                    return False, 'Jamie redeem not available'
            elif redeem_type == 'ruin':
                return False, 'Ruin day redeem not implemented'
            elif redeem_type == 'duel':
                return False, 'Duel must be triggered via !duel command'
            elif redeem_type == 'fight':
                if hasattr(bot_instance, 'fight_redeem'):
                    await bot_instance.fight_redeem.start_fight(channel, 'TestUser', 'watsonmcbot')
                else:
                    return False, 'Fight redeem not available'
            else:
                return False, 'Unknown redeem type'

            return True, None

        success, error = run_async(run_redeem())
        if not success:
            return jsonify({'error': error}), 503 if 'not available' in error else 501

        return jsonify({'message': f'{redeem_type} redeem triggered successfully'})

    except Exception as e:
        logging.error(f"Error triggering redeem: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/command/<cmd>', methods=['POST'])
@require_api_key
def api_execute_command(cmd):
    """Execute bot commands"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        import asyncio

        async def run_command():
            if cmd == 'edgestats':
                # Get edge stats
                if hasattr(bot_instance, 'edge_game_manager'):
                    stats = bot_instance.edge_game_manager.get_stats()
                    return True, f"Edge stats: {stats}"
                else:
                    return False, 'Edge game not available'
            elif cmd == 'leaderboard':
                # Get trivia leaderboard
                if hasattr(bot_instance, 'db_manager'):
                    leaders = await asyncio.to_thread(bot_instance.db_manager.get_trivia_leaderboard, limit=10)
                    if leaders:
                        result = "Trivia Leaderboard: " + ", ".join([f"{name} ({score})" for name, score in leaders[:5]])
                        return True, result
                    else:
                        return True, "No trivia stats yet"
                else:
                    return False, 'Database not available'
            elif cmd == 'triviastats':
                # Get trivia stats
                if hasattr(bot_instance, 'db_manager'):
                    stats = await asyncio.to_thread(bot_instance.db_manager.get_trivia_stats)
                    return True, f"Trivia stats: {stats}"
                else:
                    return False, 'Database not available'
            elif cmd == 'song':
                # Get current song
                if hasattr(bot_instance, 'spotify_manager'):
                    track_info = await bot_instance.spotify_manager.get_current_track()
                    if track_info:
                        return True, f"Now playing: {track_info['name']} by {track_info['artist']}"
                    else:
                        return True, "No song currently playing"
                else:
                    return False, 'Spotify not available'
            else:
                return False, 'Unknown command'

        success, message = run_async(run_command())
        if not success:
            return jsonify({'error': message}), 503
        return jsonify({'message': message})
    except Exception as e:
        logging.error(f"Error executing command: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/spotify/<action>', methods=['POST'])
@require_api_key
def api_spotify_control(action):
    """Control Spotify playback"""
    try:
        if not bot_instance or not hasattr(bot_instance, 'spotify_manager'):
            return jsonify({'error': 'Spotify not available'}), 503

        if not bot_instance.spotify_manager or not bot_instance.spotify_manager.spotify:
            return jsonify({'error': 'Spotify not connected'}), 503

        try:
            if action == 'play':
                bot_instance.spotify_manager.spotify.start_playback()
            elif action == 'pause':
                bot_instance.spotify_manager.spotify.pause_playback()
            elif action == 'next':
                bot_instance.spotify_manager.spotify.next_track()
            elif action == 'previous':
                bot_instance.spotify_manager.spotify.previous_track()
            else:
                return jsonify({'error': 'Unknown action'}), 400

            return jsonify({'message': f'Spotify {action} executed'})
        except Exception as e:
            # Spotify API errors
            return jsonify({'error': f'Spotify API error: {str(e)}'}), 500
    except Exception as e:
        logging.error(f"Error controlling Spotify: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/clear/<stats_type>', methods=['POST'])
@require_api_key
def api_clear_stats(stats_type):
    """Clear statistics"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        # This would need proper implementation based on your stats structure
        return jsonify({'message': f'{stats_type} stats cleared'})
    except Exception as e:
        logging.error(f"Error clearing stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/reload', methods=['POST'])
@require_api_key
def api_reload():
    """Reload bot (placeholder)"""
    return jsonify({'message': 'Bot reload not implemented - restart the bot manually'})

# ===== Stream Control API Endpoints =====

@app.route('/api/stream/title', methods=['POST'])
@require_api_key
def api_update_title():
    """Update stream title"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        title = data.get('title')
        if not title:
            return jsonify({'error': 'Title required'}), 400

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def update_title():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}',
                'Content-Type': 'application/json'
            }

            async with bot_instance.http_session.patch(
                f'https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}',
                headers=headers,
                json={'title': title}
            ) as response:
                if response.status == 204:
                    return True
                else:
                    error_text = await response.text()
                    logging.error(f"Failed to update title: {error_text}")
                    return False

        success = run_async(update_title())

        if success:
            return jsonify({'message': f'Stream title updated to: {title}'})
        else:
            return jsonify({'error': 'Failed to update title'}), 500
    except Exception as e:
        logging.error(f"Error updating title: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/game', methods=['POST'])
@require_api_key
def api_update_game():
    """Update stream game/category"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        game_name = data.get('game')
        if not game_name:
            return jsonify({'error': 'Game name required'}), 400

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def update_game():
            # First, get game ID
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')
            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}'
            }

            # Search for game
            async with bot_instance.http_session.get(
                f'https://api.twitch.tv/helix/games?name={game_name}',
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result['data']:
                        game_id = result['data'][0]['id']
                    else:
                        return False, 'Game not found'
                else:
                    return False, 'Failed to search for game'

            # Update channel with game ID
            broadcaster_id = await bot_instance.get_broadcaster_id()
            async with bot_instance.http_session.patch(
                f'https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}',
                headers={**headers, 'Content-Type': 'application/json'},
                json={'game_id': game_id}
            ) as response:
                if response.status == 204:
                    return True, None
                else:
                    error_text = await response.text()
                    return False, error_text

        success, error = run_async(update_game())

        if success:
            return jsonify({'message': f'Stream game updated to: {game_name}'})
        else:
            return jsonify({'error': error or 'Failed to update game'}), 500
    except Exception as e:
        logging.error(f"Error updating game: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat/<action>', methods=['POST'])
@require_api_key
def api_chat_action(action):
    """Control chat settings"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        import asyncio

        async def execute_action():
            if action == 'emote-only':
                await channel.send('/emoteonly')
                return 'Emote-only mode enabled'
            elif action == 'followers-only':
                await channel.send('/followers 10m')
                return 'Followers-only mode enabled (10 minutes)'
            elif action == 'slow-mode':
                await channel.send('/slow 30')
                return 'Slow mode enabled (30 seconds)'
            elif action == 'clear-chat':
                await channel.send('/clear')
                return 'Chat cleared'
            else:
                return None

        result = run_async(execute_action())

        if result:
            return jsonify({'message': result})
        else:
            return jsonify({'error': 'Unknown action'}), 400
    except Exception as e:
        logging.error(f"Error executing chat action: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mod/timeout', methods=['POST'])
@require_api_key
def api_timeout_user():
    """Timeout a user"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        username = data.get('username')
        duration = data.get('duration', 60)

        if not username:
            return jsonify({'error': 'Username required'}), 400

        channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        import asyncio

        async def timeout():
            await channel.send(f'/timeout {username} {duration}')

        run_async(timeout())

        return jsonify({'message': f'{username} timed out for {duration} seconds'})
    except Exception as e:
        logging.error(f"Error timing out user: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/mod/ban', methods=['POST'])
@require_api_key
def api_ban_user():
    """Ban a user"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        username = data.get('username')
        reason = data.get('reason', 'No reason provided')

        if not username:
            return jsonify({'error': 'Username required'}), 400

        channel = bot_instance.get_channel(os.getenv('CHANNEL_USERNAME'))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        import asyncio

        async def ban():
            await bot_instance.ban_user(username, reason)

        run_async(ban())

        return jsonify({'message': f'{username} has been banned: {reason}'})
    except Exception as e:
        logging.error(f"Error banning user: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/vips')
@require_api_key
def api_get_vips():
    """Get list of VIPs"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def get_vips():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}'
            }

            async with bot_instance.http_session.get(
                f'https://api.twitch.tv/helix/channels/vips?broadcaster_id={broadcaster_id}',
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return [vip['user_name'] for vip in result['data']]
                else:
                    return []

        vips = run_async(get_vips())

        return jsonify({'vips': vips})
    except Exception as e:
        logging.error(f"Error getting VIPs: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/mods')
@require_api_key
def api_get_mods():
    """Get list of moderators"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def get_mods():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}'
            }

            async with bot_instance.http_session.get(
                f'https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={broadcaster_id}',
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return [mod['user_name'] for mod in result['data']]
                else:
                    return []

        mods = run_async(get_mods())

        return jsonify({'mods': mods})
    except Exception as e:
        logging.error(f"Error getting mods: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/commercial', methods=['POST'])
@require_api_key
def api_run_commercial():
    """Run a commercial break"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        duration = data.get('duration', 30)

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def run_ad():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}',
                'Content-Type': 'application/json'
            }

            async with bot_instance.http_session.post(
                'https://api.twitch.tv/helix/channels/commercial',
                headers=headers,
                json={'broadcaster_id': broadcaster_id, 'length': duration}
            ) as response:
                return response.status == 200

        success = run_async(run_ad())

        if success:
            return jsonify({'message': f'Running {duration} second commercial'})
        else:
            return jsonify({'error': 'Failed to start commercial'}), 500
    except Exception as e:
        logging.error(f"Error running commercial: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/marker', methods=['POST'])
@require_api_key
def api_create_marker():
    """Create a stream marker"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        description = data.get('description', 'Stream marker')

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def create_marker():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}',
                'Content-Type': 'application/json'
            }

            async with bot_instance.http_session.post(
                'https://api.twitch.tv/helix/streams/markers',
                headers=headers,
                json={'user_id': broadcaster_id, 'description': description}
            ) as response:
                return response.status == 200

        success = run_async(create_marker())

        if success:
            return jsonify({'message': f'Marker created: {description}'})
        else:
            return jsonify({'error': 'Failed to create marker (stream must be live)'}), 500
    except Exception as e:
        logging.error(f"Error creating marker: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/prediction', methods=['POST'])
@require_api_key
def api_create_prediction():
    """Create a prediction"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        title = data.get('title')
        outcomes = data.get('outcomes', [])
        duration = data.get('duration', 120)

        if not title or len(outcomes) < 2:
            return jsonify({'error': 'Title and at least 2 outcomes required'}), 400

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def create_prediction():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'broadcaster_id': broadcaster_id,
                'title': title,
                'outcomes': [{'title': outcome} for outcome in outcomes],
                'prediction_window': duration
            }

            async with bot_instance.http_session.post(
                'https://api.twitch.tv/helix/predictions',
                headers=headers,
                json=payload
            ) as response:
                return response.status == 200

        success = run_async(create_prediction())

        if success:
            return jsonify({'message': f'Prediction created: {title}'})
        else:
            return jsonify({'error': 'Failed to create prediction'}), 500
    except Exception as e:
        logging.error(f"Error creating prediction: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stream/poll', methods=['POST'])
@require_api_key
def api_create_poll():
    """Create a poll"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not running'}), 503

        data = request.get_json()
        title = data.get('title')
        choices = data.get('choices', [])
        duration = data.get('duration', 120)

        if not title or len(choices) < 2:
            return jsonify({'error': 'Title and at least 2 choices required'}), 400

        import asyncio
        import aiohttp
        from config import BROADCASTER_CLIENT_ID

        async def create_poll():
            broadcaster_id = await bot_instance.get_broadcaster_id()
            broadcaster_token = await bot_instance.token_manager.get_token('broadcaster')

            headers = {
                'Client-ID': BROADCASTER_CLIENT_ID,
                'Authorization': f'Bearer {broadcaster_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'broadcaster_id': broadcaster_id,
                'title': title,
                'choices': [{'title': choice} for choice in choices],
                'duration': duration
            }

            async with bot_instance.http_session.post(
                'https://api.twitch.tv/helix/polls',
                headers=headers,
                json=payload
            ) as response:
                return response.status == 200

        success = run_async(create_poll())

        if success:
            return jsonify({'message': f'Poll created: {title}'})
        else:
            return jsonify({'error': 'Failed to create poll'}), 500
    except Exception as e:
        logging.error(f"Error creating poll: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===== Original Callback Routes =====

@app.route('/spotify/callback')
def spotify_callback():
    logging.info("Spotify callback received")
    return "Spotify callback received"

@app.route('/twitch/callback')
def twitch_callback():
    logging.info("Twitch callback received")
    return "Twitch callback received"


@app.route('/assets/images/<path:filename>')
def serve_image(filename):
    image_dir = BASE_DIR / 'overlays' / 'assets' / 'images'
    app.logger.info(f"Attempting to serve: {image_dir / filename}")
    response = send_from_directory(str(image_dir), filename)
   
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 0
    response.expires = 0
   
    return response

@app.route('/assets/videos/<path:filename>')
def serve_video(filename):
    video_dir = BASE_DIR / 'overlays' / 'assets' / 'videos'
    app.logger.info(f"Attempting to serve file: {video_dir / filename}")
   
    video_dir.mkdir(parents=True, exist_ok=True)
   
    file_path = video_dir / filename
    if not file_path.exists():
        app.logger.error(f"File not found: {file_path}")
        return Response("File not found", status=404)
    
    mime_type = 'video/mp4'
    ext = filename.lower().split('.')[-1]
    
    if ext in ['jpg', 'jpeg']:
        mime_type = 'image/jpeg'
    elif ext == 'png':
        mime_type = 'image/png'
    elif ext == 'webp':
        mime_type = 'image/webp'
    elif ext == 'gif':
        mime_type = 'image/gif'
    elif ext in ['mp4', 'mov']:
        mime_type = 'video/mp4'
    
    app.logger.info(f"Serving file with MIME type: {mime_type}")
   
    response = send_from_directory(str(video_dir), filename)
   
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 0
    response.expires = 0
   
    response.headers['Content-Type'] = mime_type
   
    return response

def run_flask():
    app.run(host=os.getenv('FLASK_HOST', '127.0.0.1'), port=int(os.getenv('FLASK_PORT', '5555')), debug=False)

if __name__ == "__main__":
    run_flask()