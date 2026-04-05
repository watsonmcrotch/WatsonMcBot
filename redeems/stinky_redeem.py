import logging
import anthropic
import asyncio
from threading import Thread
import simpleaudio as sa
import random
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

class StinkyHandler:
   def __init__(self, db_manager, sound_path: str, send_companion_event, claude=None):
       self.db_manager = db_manager
       self.sound_path = sound_path
       self.send_companion_event = send_companion_event
       self.claude = claude or anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
       self.recent_responses = []
       self.max_recent_responses = 5

   def play_sound_threaded(self, sound_path: str):
       try:
           wave_obj = sa.WaveObject.from_wave_file(sound_path)
           play_obj = wave_obj.play()
           play_obj.wait_done()
       except Exception as e:
           logging.error(f"Error playing sound: {e}")

   async def generate_stinky_comment(self, nickname: str, stink_value: int, previous_stink: Optional[int] = None) -> str:
       try:
           if stink_value <= 5:
               stink_level = "absolutely pristine"
               special_response = True
           elif stink_value >= 95:
               stink_level = "absolutely rancid"
               special_response = True
           else:
               stink_level = "average stinky"
               special_response = False
           
           stink_context = f"Current stink level: {stink_value}%"
           if previous_stink is not None:
               stink_context += f", Previous stink level: {previous_stink}%"

           recent_context = ""
           if self.recent_responses:
               recent_context = f"IMPORTANT: My recent responses were: {self.recent_responses} - Make sure your new response uses completely different words, style, structure, and approach to avoid any repetition!"

           prompt = f"""Generate a rude and humorous comment about how stinky a user is in my 18+ Twitch chat. The user's details are:
           Nickname: {nickname}
           {stink_context}
           
           Guidelines:
           - Keep it under 120 characters and simple to understand
           - Be rude but playfully so (this is expected in this chat)
           - Make reference to their stink percentage
           - {"If they're very clean (0-5%), be shocked and complimentary but still cheeky" if stink_value <= 5 else ""}
           - {"If they're extremely stinky (95-100%), be absolutely disgusted and dramatic" if stink_value >= 95 else ""}
           - {f'Compare with their previous stink level of {previous_stink}%' if previous_stink is not None else 'This is their first stink test'}
           - Be creative and vary the insults, remember cursing or swearing is fine!
           
           {recent_context}"""

           response = await asyncio.to_thread(
               self.claude.messages.create,
               model="claude-sonnet-4-5-20250929",
               max_tokens=400,
               temperature=0.8,
               system="You are a rude bot giving stinky ratings to Twitch users. Your tone is cheeky, rude, with adult humor. Always vary your responses and avoid repetition at all costs.",
               messages=[
                   {"role": "user", "content": prompt}
               ]
           )
           
           generated_comment = response.content[0].text.strip()
           
           self.recent_responses.append(generated_comment)
           if len(self.recent_responses) > self.max_recent_responses:
               self.recent_responses.pop(0)
           
           return generated_comment
           
       except Exception as e:
           logging.error(f"Error generating stinky comment: {e}")
           fallback_response = f"Bloody hell {nickname}, the stink-o-meter is broken! Try again later, you minger!"
           
           self.recent_responses.append(fallback_response)
           if len(self.recent_responses) > self.max_recent_responses:
               self.recent_responses.pop(0)
           
           return fallback_response

   async def process_stinky_redeem(self, channel, username: str, user_color: str):
       try:
           user_context = await asyncio.to_thread(self.db_manager.get_user_context, username)
           display_name = user_context.get('nickname', username)

           previous_stink = None
           if 'stink' in user_context and 'history' in user_context['stink']:
               stink_history = user_context['stink']['history']
               if stink_history:
                   previous_stink = stink_history[-1]['value']

           stink_value = random.randint(0, 100)

           try:
               await asyncio.to_thread(self.db_manager.add_stink_history, username, stink_value)
           except Exception as e:
               logging.error(f"Error storing stink value: {e}")

           stinky_comment = await self.generate_stinky_comment(display_name, stink_value, previous_stink)
          
           try:
               sound_thread = Thread(target=self.play_sound_threaded, args=(self.sound_path,))
               sound_thread.daemon = True
               sound_thread.start()
           except Exception as e:
               logging.error(f"Error playing stinky sound: {e}")

           await asyncio.sleep(0.5)

           await self.send_companion_event('reaction', {'type': 'loading', 'intensity': 1.0})

           await asyncio.sleep(3)
           
           if stink_value <= 10:
               await self.send_companion_event('reaction', {'type': 'nice', 'intensity': 1.0})
           elif stink_value >= 80:
               await self.send_companion_event('reaction', {'type': 'eww', 'intensity': 1.0})
           else:
               await self.send_companion_event('reaction', {'type': 'success', 'intensity': 1.0})

           await channel.send(f"{stinky_comment}")

       except Exception as e:
           logging.error(f"Error processing stinky redeem: {e}")
           await channel.send(f"Blimey {username}, the stink detector is buggered! Try again later!")