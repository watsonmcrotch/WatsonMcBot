import logging
import sys
import threading
import asyncio
import time
import signal
import socket
import os
from pathlib import Path
from flask import Flask
from services.flask_server import run_flask, set_bot_instance
from bot import WatsonMcBot
from services.websocket_server import (
    ws_manager,
    start_websocket_server,
    shutdown_websocket_server
)
from services.obs_client import OBSClient
from services.dashboard_broadcaster import get_broadcaster

flask_app = Flask(__name__)

@flask_app.route('/spotify/callback')
def spotify_callback():
    pass

@flask_app.route('/twitch/callback')
def twitch_callback():
    pass

async def close_service(name, service, close_func, timeout=5.0):
    if service:
        try:
            await asyncio.wait_for(close_func(service), timeout=timeout)
        except asyncio.TimeoutError:
            logging.error(f"{name} shutdown timed out")
        except Exception as e:
            logging.error(f"Error closing {name}: {e}")

async def shutdown_all(bot=None, signal_received=None):
    if signal_received:
        logging.info(f"Received signal: {signal_received}")
    
    logging.info("Starting coordinated shutdown...")
    
    try:
        if bot:
            if hasattr(bot, 'eventsub') and bot.eventsub:
                logging.info("Closing EventSub connection...")
                await bot.eventsub.close()

            if hasattr(bot, 'token_manager'):
                logging.info("Closing token manager...")
                await bot.token_manager.close()

            services = [
                ('WebSocket', shutdown_websocket_server()),
                ('OBS', bot.obs_client.disconnect() if hasattr(bot, 'obs_client') else None),
                ('Discord', bot.discord_monitor.close() if hasattr(bot, 'discord_monitor') else None),
                ('Broadcaster', bot.broadcaster.close() if hasattr(bot, 'broadcaster') else None),
                ('Database', bot.db_manager.close() if hasattr(bot, 'db_manager') else None)
            ]

            for name, close_func in services:
                try:
                    if close_func and asyncio.iscoroutine(close_func):
                        await asyncio.wait_for(close_func, timeout=5.0)
                    logging.info(f"Closed {name}")
                except Exception as e:
                    logging.error(f"Error closing {name}: {e}")

            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() 
                    if t is not current_task and not t.done()]
            
            if tasks:
                logging.info(f"Cleaning up {len(tasks)} remaining tasks...")
                for task in tasks:
                    task.cancel()
                
                if tasks:
                    try:
                        await asyncio.wait(tasks, timeout=5.0)
                    except Exception as e:
                        logging.error(f"Error in final cleanup: {e}")

    except Exception as e:
        logging.error(f"Error during shutdown: {e}", exc_info=True)
    finally:
        logging.info("Shutdown complete")

async def main_async():
    bot = None
    
    def signal_handler(sig, frame):
        logging.info(f"Received signal {sig}")
        asyncio.create_task(shutdown_all(bot, sig))

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal_handler)

    try:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logging.info("Flask server thread started")

        await start_websocket_server()
        logging.info("WebSocket server started")

        bot = WatsonMcBot()

        # Set bot instance for Flask API
        set_bot_instance(bot)
        logging.info("Bot instance registered with Flask server")

        # Initialize dashboard broadcaster
        bot.dashboard_broadcaster = get_broadcaster(ws_manager)
        logging.info("Dashboard broadcaster initialized")

        logging.info("Initializing token manager...")
        init_success = await bot.token_manager.initialize()
        if not init_success:
            logging.error("Failed to initialize token manager")
            return

        logging.info("Setting up OBS client...")
        obs_client = OBSClient(
            bot,
            host='localhost',
            port=4455,
            password=os.getenv('OBS_WEBSOCKET_PASSWORD')
        )
        obs_client.connect()
        bot.obs_client = obs_client
        logging.info("OBS client connected")
        
        logging.info("Starting WatsonMcBot...")

        from services.eventsub_client import EventSubClient
        logging.info("Initializing EventSub client...")
        bot.eventsub = EventSubClient(bot)
        eventsub_task = asyncio.create_task(bot.eventsub.connect())

        bot_task = asyncio.create_task(bot.run_all())

        await asyncio.gather(bot_task, eventsub_task)

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if bot:
            await shutdown_all(bot)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log')
        ]
    )

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logging.info("Shutting down due to keyboard interrupt...")
    except Exception as e:
        logging.error(f"Fatal error in main: {e}", exc_info=True)
    finally:
        logging.info("Program terminated")

if __name__ == "__main__":
    main()