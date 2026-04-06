import logging
import anthropic
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

class SubscriptionAlert:
    def __init__(self, bot, send_companion_event):
        self.bot = bot
        self.send_companion_event = send_companion_event
        self.video_path = "assets/videos/sub_alert.webm"
        self.claude = bot.claude
        self.recent_subs = {}
        self.COOLDOWN = 600

    async def trigger(self, username: str, data: dict):
        try:
            current_time = datetime.now()
            if username in self.recent_subs:
                last_time = self.recent_subs[username]
                if (current_time - last_time).total_seconds() < self.COOLDOWN:
                    logging.info(f"Skipping duplicate sub alert for {username} - cooldown active")
                    return
            self.recent_subs[username] = current_time

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            is_resub = data.get('is_resub', False)
            tier = str(data.get('tier', '1000'))
            is_prime = data.get('is_prime', False)
            streak_months = data.get('streak_months', 0)
            cumulative_months = data.get('cumulative_months', 0)
            
            sub_type = "resubscribed!" if is_resub else "subscribed!"

            # Trigger WatsonOS browser overlay sub alert
            if hasattr(self.bot, 'overlay_manager'):
                asyncio.create_task(self.bot.overlay_manager.trigger_sub_alert(
                    username, tier, is_resub, cumulative_months, display_name=display_name))

            sub_info = {
                'display_name': display_name,
                'is_resub': is_resub,
                'is_prime': is_prime,
                'streak_months': streak_months,
                'cumulative_months': cumulative_months,
                'tier': tier
            }
            chat_message = await self.generate_sub_message(sub_info)
            
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if channel:
                await channel.send(chat_message)

        except Exception as e:
            logging.error(f"Error processing subscription alert: {e}")

    async def generate_sub_message(self, sub_info: dict) -> str:
        try:
            sub_type = "resubscribed" if sub_info['is_resub'] else "subscribed"
            tier_num = int(sub_info['tier']) // 1000
            
            if sub_info['is_prime']:
                sub_method = "with Prime"
            elif tier_num > 1:
                sub_method = f"at Tier {tier_num}"
            else:
                sub_method = ""
            
            streak_info = ""
            total_months = ""
            
            if sub_info['is_resub']:
                if sub_info['cumulative_months'] > 0:
                    total_months = f" for a total of {sub_info['cumulative_months']} months"
                
                if sub_info['streak_months'] > 0:
                    streak_info = f" ({sub_info['streak_months']} months consecutive)"

            prompt = f"""Create an enthusiastic thank you message for a Twitch subscriber. Details:
            - User: {sub_info['display_name']}
            - Action: {sub_type} {sub_method}{total_months}{streak_info}
            
            Guidelines:
            - Keep response under 300 characters
            - Be enthusiastic but not over-the-top
            - Include adult humor where appropriate
            - Make the message personal and appreciative
            - Only mention tier/prime if specified
            - Distinguish total time subbed from streak when both are present but don't point out gaps in streaks"""

            response = await asyncio.to_thread(
                self.claude.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=800,
                temperature=0.7,
                system="You are a Twitch bot creating personalized thank you messages for subscribers.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            return str(response.content[0].text)[:300]

        except Exception as e:
            logging.error(f"Error generating subscription message: {e}")
            return f"Thank you for {'resubscribing' if sub_info['is_resub'] else 'subscribing'}, {sub_info['display_name']}!"