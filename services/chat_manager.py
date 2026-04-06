import logging
from typing import Dict, List
from datetime import datetime
from services.websocket_server import ws_manager

class ChatHandler:
    def __init__(self, bot, send_companion_event):
        self.bot = bot
        self.send_companion_event = send_companion_event

    def parse_emotes_string(self, emotes_str: str) -> Dict[str, List[str]]:
        emotes = {}
        try:
            if not emotes_str:
                return emotes
            emote_entries = emotes_str.split('/')
            for entry in emote_entries:
                if not entry:
                    continue
                emote_id, positions_str = entry.split(':')
                positions = positions_str.split(',')
                emotes[emote_id] = positions
        except Exception as e:
            logging.error(f"Error parsing emotes string: {e}", exc_info=True)
        return emotes

    def parse_twitch_emotes(self, message_data: Dict) -> List[Dict]:
        fragments = []
        try:
            if isinstance(message_data, dict) and 'emotes' in message_data:
                emote_positions = []
                for emote_id, positions in message_data['emotes'].items():
                    for position in positions:
                        start, end = map(int, position.split('-'))
                        emote_name = message_data['text'][start:end+1]
                        emote_positions.append({
                            'start': start,
                            'end': end,
                            'emote': {
                                'type': 'twitch_emote',
                                'id': emote_id,
                                'name': emote_name,
                                'url': f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/2.0"
                            }
                        })
                emote_positions.sort(key=lambda x: x['start'])
                last_pos = 0
                for pos in emote_positions:
                    if pos['start'] > last_pos:
                        text = message_data['text'][last_pos:pos['start']]
                        fragments.extend(self.parse_seventv_emotes(text))
                    fragments.append(pos['emote'])
                    last_pos = pos['end'] + 1
                if last_pos < len(message_data['text']):
                    text = message_data['text'][last_pos:]
                    fragments.extend(self.parse_seventv_emotes(text))
        except Exception as e:
            logging.error(f"Error parsing Twitch emotes: {e}", exc_info=True)
        return fragments

    def parse_seventv_emotes(self, message: str) -> List[Dict]:
        fragments = []
        words = message.split()
        for word in words:
            if word in self.bot.emote_tracker.seventv_emotes:
                emote = self.bot.emote_tracker.seventv_emotes[word]
                fragments.append({
                    'type': '7tv_emote',
                    'name': word,
                    'url': f"https://cdn.7tv.app/emote/{emote['id']}/1x.avif",
                    'animated': emote.get('animated', False)
                })
            elif word.startswith('@') and len(word) > 1:
                mentioned = word[1:].lower().rstrip('.,!?:;')
                mention_color = None
                try:
                    ctx = self.bot.db_manager.get_user_context(mentioned)
                    mention_color = ctx.get('color')
                except Exception:
                    pass
                fragments.append({
                    'type': 'mention',
                    'content': word + ' ',
                    'username': mentioned,
                    'color': mention_color
                })
            else:
                fragments.append({
                    'type': 'text',
                    'content': word + ' '
                })
        return fragments

    def parse_message(self, message: str, message_data: Dict = None) -> List[Dict]:
        fragments = []
        if message_data and 'emotes' in message_data:
            emotes = message_data['emotes']
            if isinstance(emotes, str):
                emotes = self.parse_emotes_string(emotes)
            fragments = self.parse_twitch_emotes({'text': message, 'emotes': emotes})
        else:
            fragments = self.parse_seventv_emotes(message)
        return fragments

    async def process_chat_message(self, username: str, message: str, user_color: str = None, message_data: Dict = None):
        try:
            if message.strip().startswith('!'):
                return
                
            user_context = self.bot.db_manager.get_user_context(username)
            display_name = user_context.get('nickname', username)
            if not user_color:
                user_color = user_context.get('color', '#FF69B4')
            fragments = self.parse_message(message, message_data)
            await self.send_companion_event('chat-message', {
                'username': username,
                'displayName': display_name,
                'message': message,
                'fragments': fragments,
                'userColor': user_color,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Error processing chat message: {e}", exc_info=True)
