import asyncio
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Callable
from dotenv import load_dotenv, set_key

class TwitchTokenManager:
    def __init__(self, bot_client_id: str, bot_client_secret: str,
                 broadcaster_client_id: str, broadcaster_client_secret: str):
        self.bot_client_id = bot_client_id
        self.bot_client_secret = bot_client_secret
        self.broadcaster_client_id = broadcaster_client_id
        self.broadcaster_client_secret = broadcaster_client_secret
        self.env_file = '.env'
        self._tokens = {
            'bot': {'access': None, 'refresh': None, 'expires_at': None},
            'broadcaster': {'access': None, 'refresh': None, 'expires_at': None}
        }
        self._token_refresh_tasks = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._token_refresh_callbacks: Set[Callable] = set()
        self._running = False

    async def initialize(self) -> bool:
        try:
            logging.info("Starting token manager initialization...")
            
            self._tokens['bot']['access'] = os.getenv('BOT_ACCESS_TOKEN', '').strip("'").strip('"')
            self._tokens['bot']['refresh'] = os.getenv('BOT_REFRESH_TOKEN', '').strip("'").strip('"')
            self._tokens['broadcaster']['access'] = os.getenv('TWITCH_READ_TOKEN', '').strip("'").strip('"')
            self._tokens['broadcaster']['refresh'] = os.getenv('TWITCH_READ_REFRESH_TOKEN', '').strip("'").strip('"')

            results = await asyncio.gather(
                self.validate_token('bot'),
                self.validate_token('broadcaster'),
                return_exceptions=True
            )

            if all(isinstance(result, bool) and result for result in results):
                self._initialized = True
                self._running = True
                return True

            logging.error("Token validation failed during initialization")
            return False

        except Exception as e:
            logging.error(f"Error initializing token manager: {e}")
            return False

    def register_refresh_callback(self, callback: Callable):
        self._token_refresh_callbacks.add(callback)
        logging.info(f"Registered new token refresh callback. Total callbacks: {len(self._token_refresh_callbacks)}")

    async def schedule_token_refresh(self, account_type: str, expires_in: int):
        if account_type in self._token_refresh_tasks:
            self._token_refresh_tasks[account_type].cancel()

        refresh_delay = max(0, expires_in - 300)

        async def delayed_refresh():
            await asyncio.sleep(refresh_delay)
            if self._running:
                success = await self.refresh_token(account_type)
                if success:
                    for callback in self._token_refresh_callbacks:
                        try:
                            await callback(account_type)
                        except Exception as e:
                            logging.error(f"Error in token refresh callback: {e}")

        self._token_refresh_tasks[account_type] = asyncio.create_task(delayed_refresh())

    async def get_token(self, account_type: str) -> Optional[str]:
        try:
            if not self._initialized:
                logging.error("Token manager not initialized")
                return None

            async with self._lock:
                if not self._tokens[account_type]['access']:
                    if not await self.refresh_token(account_type):
                        return None

                return self._tokens[account_type]['access']

        except Exception as e:
            logging.error(f"Error getting token for {account_type}: {e}")
            return None

    async def validate_token(self, account_type: str) -> bool:
        try:
            token = self._tokens[account_type]['access']
            client_id = self.bot_client_id if account_type == 'bot' else self.broadcaster_client_id

            if not token:
                logging.warning(f"No token available for {account_type}, attempting refresh")
                return await self.refresh_token(account_type)

            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Client-ID': client_id
                }
                
                async with session.get('https://id.twitch.tv/oauth2/validate', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        expires_in = data['expires_in']
                        
                        await self.schedule_token_refresh(account_type, expires_in)
                        self._tokens[account_type]['expires_at'] = datetime.now() + timedelta(seconds=expires_in)
                        
                        logging.info(f"Token validated successfully for {account_type}")
                        return True
                    
                    logging.warning(f"Token validation failed for {account_type} with status {response.status}")
                    error_data = await response.text()
                    logging.warning(f"Validation error response: {error_data}")

                    return await self.refresh_token(account_type)

        except aiohttp.ClientError as e:
            logging.error(f"Network error validating token for {account_type}: {e}")
            return False
        except Exception as e:
            logging.error(f"Error validating token for {account_type}: {e}")
            return False

    async def refresh_token(self, account_type: str) -> bool:
        async with self._lock:
            try:
                refresh_token = self._tokens[account_type]['refresh']
                if not refresh_token:
                    logging.error(f"No refresh token available for {account_type}")
                    return False

                client_id = self.bot_client_id if account_type == 'bot' else self.broadcaster_client_id
                client_secret = self.bot_client_secret if account_type == 'bot' else self.broadcaster_client_secret

                logging.info(f"Attempting to refresh token for {account_type}")
                async with aiohttp.ClientSession() as session:
                    data = {
                        'client_id': client_id,
                        'client_secret': client_secret,
                        'grant_type': 'refresh_token',
                        'refresh_token': refresh_token
                    }
                    
                    async with session.post('https://id.twitch.tv/oauth2/token', data=data) as response:
                        if response.status == 200:
                            token_data = await response.json()
                            self._tokens[account_type]['access'] = token_data['access_token']
                            self._tokens[account_type]['refresh'] = token_data['refresh_token']
                            expires_in = token_data.get('expires_in', 3600)
                            
                            await self.schedule_token_refresh(account_type, expires_in)
                            self._tokens[account_type]['expires_at'] = datetime.now() + timedelta(seconds=expires_in)

                            await self._update_env_tokens(account_type, token_data)
                            
                            logging.info(f"Successfully refreshed token for {account_type}")
                            return True
                            
                        error_data = await response.text()
                        logging.error(f"Failed to refresh {account_type} token. Status: {response.status}, Error: {error_data}")
                        return False

            except aiohttp.ClientError as e:
                logging.error(f"Network error refreshing token for {account_type}: {e}")
                return False
            except Exception as e:
                logging.error(f"Error refreshing {account_type} token: {e}")
                return False

    async def _update_env_tokens(self, account_type: str, token_data: Dict) -> None:
        try:
            if account_type == 'bot':
                set_key(self.env_file, 'BOT_ACCESS_TOKEN', token_data['access_token'])
                set_key(self.env_file, 'BOT_REFRESH_TOKEN', token_data['refresh_token'])
                os.environ['BOT_ACCESS_TOKEN'] = token_data['access_token']
                os.environ['BOT_REFRESH_TOKEN'] = token_data['refresh_token']
            else:
                set_key(self.env_file, 'TWITCH_READ_TOKEN', token_data['access_token'])
                set_key(self.env_file, 'TWITCH_READ_REFRESH_TOKEN', token_data['refresh_token'])
                os.environ['TWITCH_READ_TOKEN'] = token_data['access_token']
                os.environ['TWITCH_READ_REFRESH_TOKEN'] = token_data['refresh_token']
            
        except Exception as e:
            logging.error(f"Error updating environment tokens for {account_type}: {e}")

    async def close(self) -> None:
        self._running = False
        for task in self._token_refresh_tasks.values():
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._initialized = False
        self._token_refresh_tasks.clear()
        logging.info("Token manager shut down successfully")