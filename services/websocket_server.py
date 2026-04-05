import asyncio
import json
import logging
import weakref
from typing import Set
from urllib.parse import urlparse, parse_qs
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
import os

class WebSocketErrorFilter(logging.Filter):
    def filter(self, record):
        if record.name == 'websockets.server' and 'EOFError' in record.getMessage():
            return False
        if 'opening handshake failed' in record.getMessage():
            return False
        return True

logging.getLogger('websockets.server').addFilter(WebSocketErrorFilter())

WEB_SERVER_URL = f'http://{os.getenv("FLASK_HOST", "localhost")}:{os.getenv("FLASK_PORT", "5555")}'

WS_API_KEY = os.getenv('DASHBOARD_API_KEY')

class WebSocketManager:
    def __init__(self, host='localhost', port=8555):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.running = False
        self.output_queue = asyncio.Queue()
        self._cleanup_task = None

    async def broadcast(self, message):
        if not self.clients:
            return

        try:
            message_json = json.dumps(message)
        except (TypeError, ValueError) as e:
            logging.error(f"Failed to serialize message: {e}")
            return

        connections_copy = self.clients.copy()
        disconnected = set()
        successful_broadcasts = 0

        for websocket in connections_copy:
            try:
                if hasattr(websocket, 'closed') and websocket.closed:
                    disconnected.add(websocket)
                    continue
                    
                await websocket.send(message_json)
                successful_broadcasts += 1
                
            except ConnectionClosed:
                disconnected.add(websocket)
            except WebSocketException as e:
                logging.warning(f"WebSocket send error: {e}")
                disconnected.add(websocket)
            except Exception as e:
                logging.error(f"Unexpected error sending message: {e}")
                disconnected.add(websocket)

        self.clients -= disconnected
        
        if disconnected:
            logging.info(f"Cleaned up {len(disconnected)} disconnected WebSocket connections")

    async def handler(self, websocket, path=None):
        client_id = id(websocket)

        try:
            try:
                client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            except Exception:
                client_address = "unknown"

            # Authenticate via ?token= query parameter
            if WS_API_KEY:
                ws_path = websocket.request.path if hasattr(websocket, 'request') else getattr(websocket, 'path', '/')
                params = parse_qs(urlparse(ws_path).query)
                token = params.get('token', [None])[0]
                if token and token != WS_API_KEY:
                    logging.warning(f"WebSocket auth failed from {client_address}")
                    await websocket.close(4001, "Unauthorized")
                    return

            logging.info(f"New WebSocket connection from {client_address} (ID: {client_id})")
            self.clients.add(websocket)
            logging.info(f"Total clients: {len(self.clients)}")

            await websocket.wait_closed()
            
        except ConnectionClosed:
            pass
        except WebSocketException as e:
            if "1000" not in str(e):
                pass
        except EOFError:
            pass
        except Exception as e:
            logging.error(f"Unexpected error in WebSocket handler for {client_address}: {e}")
        finally:
            self.clients.discard(websocket)
            logging.info(f"Client {client_id} disconnected. {len(self.clients)} clients remaining")

    async def start_server(self):
        if self.running:
            return

        self.running = True
        try:
            self.server = await websockets.serve(
                self.handler,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=10,
                max_size=2**20,
                compression=None
            )
            
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logging.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            
        except Exception as e:
            self.running = False
            logging.error(f"Failed to start WebSocket server: {e}")
            raise

    async def _periodic_cleanup(self):
        while self.running:
            try:
                await asyncio.sleep(30)
                
                disconnected = set()
                for websocket in self.clients.copy():
                    if hasattr(websocket, 'closed') and websocket.closed:
                        disconnected.add(websocket)
                
                self.clients -= disconnected
                
                if disconnected:
                    logging.info(f"Periodic cleanup removed {len(disconnected)} dead connections")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in periodic cleanup: {e}")

    async def stop_server(self):
        if not self.running:
            return

        logging.info("Stopping WebSocket server...")
        self.running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        await self.close_all()

        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
            except Exception as e:
                logging.error(f"Error closing server: {e}")
            finally:
                self.server = None

        logging.info("WebSocket server stopped")

    async def close_all(self):
        if self.clients:
            logging.info(f"Closing {len(self.clients)} WebSocket connections")
            
            close_tasks = []
            for websocket in self.clients.copy():
                if not (hasattr(websocket, 'closed') and websocket.closed):
                    close_tasks.append(websocket.close(code=1000, reason="Server shutting down"))
            
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            
            self.clients.clear()


ws_manager = WebSocketManager()
output_queue = ws_manager.output_queue


async def start_websocket_server():
    await ws_manager.start_server()


async def shutdown_websocket_server():
    try:
        logging.info("Starting WebSocket server shutdown...")
        await ws_manager.stop_server()
        logging.info("WebSocket server shutdown complete")
    except Exception as e:
        logging.error(f"Error during WebSocket server shutdown: {e}")


async def queue_message(message):
    if ws_manager.running:
        await ws_manager.broadcast(message)
        await output_queue.put(message)


__all__ = [
    'ws_manager',
    'output_queue', 
    'start_websocket_server',
    'shutdown_websocket_server',
    'WEB_SERVER_URL'
]