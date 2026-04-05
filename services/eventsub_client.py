import asyncio
import aiohttp
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Set

class EventSubClient:
    def __init__(self, bot):
        self.bot = bot
        self.ws = None
        self.session = None
        self._running = False
        self.session_id = None
        self.reconnect_attempt = 0
        self.max_reconnect_delay = 300
        self._last_heartbeat = datetime.now()
        self.heartbeat_interval = 30
        self.subscribed_events = set()
        self.connection_ready = asyncio.Event()
        self.connect_task = None
        self._lock = asyncio.Lock()

        self.sub_types = {
            'channel.follow': {'version': '2', 'needs_moderator': True},
            'channel.subscribe': {'version': '1', 'needs_moderator': False},
            'channel.subscription.message': {'version': '1', 'needs_moderator': False},
            'channel.subscription.gift': {'version': '1', 'needs_moderator': False},
            'channel.cheer': {'version': '1', 'needs_moderator': False},
            'channel.raid': {'version': '1', 'needs_moderator': False, 'to_broadcaster': True},
            'channel.channel_points_custom_reward_redemption.add': {'version': '1', 'needs_moderator': False}
        }

    async def initialize(self) -> bool:
        try:
            self.bot.token_manager.register_refresh_callback(self.handle_token_refresh)
            self.connect_task = asyncio.create_task(self.connect())
            return True
        except Exception as e:
            logging.error(f"Error initializing EventSub client: {e}")
            return False

    async def handle_token_refresh(self, account_type: str):
        if account_type == 'broadcaster':
            async with self._lock:
                logging.info("Broadcaster token refreshed, revalidating subscriptions")
                self.subscribed_events.clear()
                await self.subscribe_to_events()

    async def get_auth_headers(self) -> Dict[str, str]:
        broadcaster_token = await self.bot.token_manager.get_token('broadcaster')
        if not broadcaster_token:
            raise Exception("Failed to get broadcaster token")
            
        return {
            'Client-ID': self.bot.broadcaster_client_id,
            'Authorization': f'Bearer {broadcaster_token}',
            'Content-Type': 'application/json'
        }

    def _get_subscription_condition(self, sub_type: str, config: Dict) -> Dict:
        condition = {'broadcaster_user_id': self.bot._channel_id}
        
        if sub_type == 'channel.raid' and config.get('to_broadcaster'):
            condition = {'to_broadcaster_user_id': self.bot._channel_id}
            
        if config.get('needs_moderator'):
            condition['moderator_user_id'] = self.bot._channel_id
            
        return condition

    async def connect(self):
        while True:
            try:
                if self.ws:
                    await self.ws.close()
                if self.session:
                    await self.session.close()

                self.session = aiohttp.ClientSession()

                if self.reconnect_attempt > 0:
                    logging.warning(f"EventSub reconnecting (attempt {self.reconnect_attempt})...")
                else:
                    logging.info("EventSub connecting...")

                self.ws = await self.session.ws_connect(
                    'wss://eventsub.wss.twitch.tv/ws',
                    heartbeat=self.heartbeat_interval,
                    timeout=30
                )
                self._running = True
                self.reconnect_attempt = 0

                logging.info("EventSub WebSocket connected successfully")

                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                        await self._handle_message(data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        logging.error("EventSub WebSocket closed unexpectedly")
                        raise aiohttp.ClientError("WebSocket closed unexpectedly")

            except asyncio.CancelledError:
                logging.warning("EventSub connection cancelled")
                break
            except Exception as e:
                logging.error(f"EventSub connection error: {e}")
                if self._running:
                    await self._handle_reconnect()
                else:
                    break

    async def _handle_reconnect(self):
        self._running = False
        self.connection_ready.clear()
        
        delay = min(2 ** self.reconnect_attempt, self.max_reconnect_delay)
        self.reconnect_attempt += 1
        
        await asyncio.sleep(delay)
        if not self.connect_task or self.connect_task.done():
            self.connect_task = asyncio.create_task(self.connect())

    async def _handle_message(self, msg: Dict):
        try:
            message_type = msg['metadata']['message_type']

            if message_type == 'session_welcome':
                self.session_id = msg['payload']['session']['id']
                self.connection_ready.set()
                await self.subscribe_to_events()

            elif message_type == 'notification':
                await self.bot.handle_eventsub_notification(
                    msg['metadata']['subscription_type'],
                    msg['payload']['event']
                )

            elif message_type == 'session_reconnect':
                reconnect_url = msg['payload']['session']['reconnect_url']
                await self._handle_reconnect_message(reconnect_url)

            elif message_type == 'revocation':
                await self._handle_revocation(msg['payload'])

        except Exception as e:
            logging.error(f"Error handling EventSub message: {e}")

    async def _handle_reconnect_message(self, reconnect_url: str):
        try:
            if self.ws:
                await self.ws.close()
            if self.session:
                await self.session.close()

            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(reconnect_url)
            
        except Exception as e:
            logging.error(f"Error during EventSub reconnection: {e}")
            await self._handle_reconnect()

    async def subscribe_to_events(self) -> bool:
        if not self.session_id:
            return False

        try:
            headers = await self.get_auth_headers()
            subscription_status = {}
            
            for sub_type, config in self.sub_types.items():
                subscription_status[sub_type] = False

                subscription_data = {
                    'type': sub_type,
                    'version': config['version'],
                    'condition': self._get_subscription_condition(sub_type, config),
                    'transport': {
                        'method': 'websocket',
                        'session_id': self.session_id
                    }
                }

                async with self.session.post(
                    'https://api.twitch.tv/helix/eventsub/subscriptions',
                    headers=headers,
                    json=subscription_data
                ) as response:
                    if response.status in [200, 202]:
                        self.subscribed_events.add(sub_type)
                        subscription_status[sub_type] = True
                    else:
                        response_text = await response.text()
                        if "subscription already exists" in response_text.lower():
                            self.subscribed_events.add(sub_type)
                            subscription_status[sub_type] = True

                await asyncio.sleep(0.5)

            logging.info("\nEventSub Subscription Status:")
            logging.info("═══════════════════════════")
            for sub_type, status in subscription_status.items():
                icon = "✓" if status else "✗"
                status_text = "SUCCESS" if status else "FAILED "
                logging.info(f"{icon} {status_text} - {sub_type}")
            logging.info("═══════════════════════════\n")

            return all(subscription_status.values())

        except Exception as e:
            logging.error(f"Error in subscribe_to_events: {e}")
            return False

    async def _handle_revocation(self, payload: Dict):
        sub_type = payload.get('subscription', {}).get('type')
        if sub_type:
            self.subscribed_events.discard(sub_type)
            if self._running:
                await self.subscribe_to_events()

    async def close(self):
        self._running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        if self.connect_task and not self.connect_task.done():
            self.connect_task.cancel()
            try:
                await self.connect_task
            except asyncio.CancelledError:
                pass