import asyncio
import os
import random
import logging
from datetime import datetime
from threading import Thread
from twitchio.ext import commands
from typing import Optional
from config import BASE_DIR


class StreamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='emotes', aliases=['emote', 'emotelist'])
    async def get_emote_stats(self, ctx, username: str = None):
        try:
            current_time = datetime.now()

            if hasattr(self.bot, '_last_emotes_time'):
                time_since_last = (current_time - self.bot._last_emotes_time).total_seconds()
                if time_since_last < 5:
                    await ctx.send(f"Woah there! Let me catch my breath for {5 - time_since_last:.1f}s!")
                    return

            self.bot._last_emotes_time = current_time

            target_user = username.lower() if username else ctx.author.name.lower().lstrip('@')
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
            display_name = user_context.get('nickname', target_user)

            top_emotes = self.bot.emote_tracker.get_top_emotes(target_user)
            if not top_emotes:
                await ctx.send(f"No emote stats found for {display_name}")
                self.bot.log_message(f"No emote stats found for {display_name}", 'system')
                return

            stats = " | ".join(f"{emote} : {count}" for emote, count in top_emotes)
            response = f"{display_name}'s most used emotes: {stats}"
            await ctx.send(response)
            self.bot.log_message(response, 'system')
        except Exception as e:
            self.bot.log_error(f"Error in get_emote_stats command: {e}")
            await ctx.send("Sorry, I couldn't retrieve emote stats at the moment.")

    @commands.command(name='topemotes')
    async def get_global_top_emotes(self, ctx):
        try:
            top_emotes = self.bot.emote_tracker.get_top_emotes(username=None)
            if not top_emotes:
                await ctx.send("No emote stats available yet!")
                return

            stats = " | ".join(f"{emote} : {count}" for emote, count in top_emotes)
            response = f"Channel's most used emotes: {stats}"
            await ctx.send(response)
            self.bot.log_message(response, 'system')
        except Exception as e:
            self.bot.log_error(f"Error in get_global_top_emotes command: {e}")
            await ctx.send("Sorry, I couldn't retrieve global emote stats at the moment.")

    @commands.command(name='replay')
    async def replay_video(self, ctx):
        try:
            if not ctx.author.is_mod and ctx.author.name.lower() != self.bot.streamer_name.lower():
                await ctx.send("Only mods and the streamer can replay videos!")
                return

            if not hasattr(self.bot, 'video_redeem'):
                await ctx.send("Video redeem system is not initialized!")
                return

            success = await self.bot.video_redeem.handle_replay_command(
                ctx.channel,
                ctx.author.name.lower(),
                self.bot.streamer_name.lower()
            )

            if success:
                self.bot.log_message(f"Video replay triggered by {ctx.author.name}", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in replay_video command: {e}")
            await ctx.send("Sorry, couldn't replay the video at the moment.")

    @commands.command(name='stinky', aliases=['stink', 'smelly', 'smell'])
    async def stinky_command(self, ctx, target_user: Optional[str] = None):
        try:
            username = target_user.lower().strip('@') if target_user else ctx.author.name.lower().lstrip('@')
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)

            if not user_context or 'stink' not in user_context or 'history' not in user_context['stink']:
                await ctx.send(f"No stink readings found for {username}! They need to use the stinky redeem first!")
                return

            display_name = user_context.get('nickname', username)
            stink_data = user_context['stink']

            current_stink = stink_data['current']
            average_stink = stink_data['average']
            stink_history = stink_data['history']

            previous_stink = None
            if len(stink_history) > 1:
                previous_stink = stink_history[-2]['value']

            def get_stink_description(value):
                if value <= 5:
                    return "Absolutely Fresh"
                elif value <= 15:
                    return "Pretty Clean"
                elif value <= 30:
                    return "Slightly Pongy"
                elif value <= 50:
                    return "Moderately Manky"
                elif value <= 70:
                    return "Properly Stinky"
                elif value <= 85:
                    return "Absolutely Rank"
                elif value <= 95:
                    return "Disgustingly Rancid"
                else:
                    return "TOXIC WASTE LEVEL"

            current_desc = get_stink_description(current_stink)

            message = f"{display_name}'s Stink Report - Current: {current_stink}% ({current_desc})"

            if previous_stink is not None:
                change = current_stink - previous_stink
                if change > 0:
                    message += f" | Last: {previous_stink}% (+{change}%)"
                elif change < 0:
                    message += f" | Last: {previous_stink}% ({change}%)"
                else:
                    message += f" | Last: {previous_stink}% (No change)"

            message += f" | Average: {average_stink}%"

            await ctx.send(message)

        except Exception as e:
            logging.error(f"Error in stinky command: {e}")
            await ctx.send(f"Failed to read {username}'s stink levels... The stink-o-meter must be broken!")

    @commands.command(name='nickname')
    async def get_nickname_cmd(self, ctx, username: str = None):
        try:
            target_user = (username or ctx.author.name).lower().lstrip('@')

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
            if not user_context:
                await ctx.send(f"No data found for user {target_user}")
                return

            nickname = user_context.get('nickname', target_user)
            if nickname != target_user:
                response = f"{target_user} = {nickname}"
                await ctx.send(response)
                self.bot.log_message(response, 'system')
            else:
                response = f"No nickname set for {target_user}."
                await ctx.send(response)
                self.bot.log_message(response, 'system')
        except Exception as e:
            self.bot.log_error(f"Error in get_nickname_cmd: {e}")
            await ctx.send("Sorry, I encountered an error while retrieving the nickname.")

    @commands.command(name='setprompt')
    async def set_custom_prompt(self, ctx, username: str = None, *, prompt: str = None):
        try:
            if ctx.author.name.lower() != os.getenv('CHANNEL_USERNAME').lower():
                await ctx.send("Sorry, this is a broadcaster-only command!")
                return

            if not username or not prompt:
                await ctx.send("Usage: !setprompt <username> <custom instruction>")
                return

            target_user = username.lower().lstrip('@')

            await asyncio.to_thread(self.bot.db_manager.set_custom_prompt, target_user, prompt)

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
            display_name = user_context.get('nickname', target_user)

            await ctx.send(f"Custom prompt set for {display_name}!")
            self.bot.log_message(f"Custom prompt set for {target_user}: {prompt}", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in set_custom_prompt: {e}")
            await ctx.send("Sorry, something went wrong setting the custom prompt!")

    @commands.command(name='removeprompt')
    async def remove_custom_prompt(self, ctx, username: str = None):
        try:
            if ctx.author.name.lower() != os.getenv('CHANNEL_USERNAME').lower():
                await ctx.send("Sorry, this is a broadcaster-only command!")
                return

            if not username:
                await ctx.send("Usage: !removeprompt <username>")
                return

            target_user = username.lower().lstrip('@')

            removed = await asyncio.to_thread(self.bot.db_manager.remove_custom_prompt, target_user)

            if removed:
                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
                display_name = user_context.get('nickname', target_user)
                await ctx.send(f"Custom prompt removed for {display_name}!")
                self.bot.log_message(f"Custom prompt removed for {target_user}", 'system')
            else:
                await ctx.send(f"No custom prompt found for {target_user}.")

        except Exception as e:
            self.bot.log_error(f"Error in remove_custom_prompt: {e}")
            await ctx.send("Sorry, something went wrong removing the custom prompt!")

    @commands.command(name='viewprompt')
    async def view_custom_prompt(self, ctx, username: str = None):
        try:
            if ctx.author.name.lower() != os.getenv('CHANNEL_USERNAME').lower():
                await ctx.send("Sorry, this is a broadcaster-only command!")
                return

            if not username:
                await ctx.send("Usage: !viewprompt <username>")
                return

            target_user = username.lower().lstrip('@')

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
            display_name = user_context.get('nickname', target_user)

            if 'custom_prompt' in user_context and user_context['custom_prompt']:
                await ctx.send(f"{display_name}'s custom prompt: {user_context['custom_prompt']}")
            else:
                await ctx.send(f"No custom prompt set for {display_name}.")

        except Exception as e:
            self.bot.log_error(f"Error in view_custom_prompt: {e}")
            await ctx.send("Sorry, something went wrong viewing the custom prompt!")

    @commands.command(name='rizz')
    async def rizz_command(self, ctx, target: str = None):
        try:
            from bot import play_sound

            current_time = datetime.now()
            username = ctx.author.name.lower()
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            if random.random() < 0.1:
                await self.bot.send_companion_event('reaction', {'type': 'rizz', 'intensity': 1.2})
            else:
                await self.bot.send_companion_event('reaction', {'type': 'heart', 'intensity': 1.2})

            if hasattr(self.bot, '_last_rizz_time'):
                time_since_last = (current_time - self.bot._last_rizz_time).total_seconds()
                if time_since_last < 60:
                    cooldown_messages = [
                        f"Calm down rizz master {display_name}, try again in {(60 - time_since_last):.1f} seconds!",
                        f"Your rizz tank is empty {display_name}! Refilling in {(60 - time_since_last):.1f} seconds...",
                        f"Too much rizz might cause an explosion {display_name}! Wait {(60 - time_since_last):.1f} seconds!",
                        f"Your rizz license is on cooldown for {(60 - time_since_last):.1f} seconds, {display_name}!",
                        f"Slow down {display_name}! Your rizz powers need {(60 - time_since_last):.1f} more seconds to regenerate!",
                        f"Even the smoothest operators need {(60 - time_since_last):.1f} seconds between rizz attempts, {display_name}!",
                        f"Your rizz battery is at 10%! Charging for {(60 - time_since_last):.1f} more seconds, {display_name}!",
                        f"The Rizz Department has placed you on a {(60 - time_since_last):.1f} second timeout, {display_name}!",
                    ]
                    await ctx.send(random.choice(cooldown_messages))
                    return

            self.bot._last_rizz_time = current_time

            if not target:
                random_targets = [
                    "everyone in chat",
                    "the whole stream",
                    "all the viewers",
                    "anyone watching",
                    "the entire chat",
                    "everybody here"
                ]
                target_display = random.choice(random_targets)
            else:
                target_username = target.lower().lstrip('@')
                target_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_username)
                target_display = target_context.get('nickname', target_username)

            def play_sound_threaded(sound_path, volume):
                try:
                    play_sound(sound_path, volume=volume)
                except Exception as e:
                    logging.error(f"Error playing sound: {e}")

            try:
                sound_thread = Thread(target=play_sound_threaded,
                args=(str(BASE_DIR / 'sounds' / 'rizz.mp3'), 0.5))
                sound_thread.daemon = True
                sound_thread.start()
            except Exception as e:
                logging.error(f"Error playing rizz sound: {e}")

            rizz_messages = [
                f"{display_name} is shooting their shot at {target_display}!",
                f"Damn {display_name}, smooth operator alert rizzin' up {target_display}!",
                f"{display_name} tryna rizz up {target_display}... will it work though?",
                f"{display_name} putting in the work on {target_display}!",
                f"Spicy! {display_name} with the moves on {target_display}!",
                f"{display_name}'s got game and {target_display} is the target!",
                f"Is {display_name} really bout to bag {target_display}? We'll see...",
                f"{display_name} coming in hot with the rizz on {target_display}!",
                f"Smooth like butter, {display_name} trying to charm {target_display}!",
                f"{display_name} manifesting a connection with {target_display}!",
                f"Watch out {target_display}, {display_name}'s got their eyes on you!",
                f"The chemistry between {display_name} and {target_display} is... experimental!",
                f"{display_name} riding the wave of confidence towards {target_display}!",
                f"{display_name} playing all the right notes to impress {target_display}!",
                f"Setting the mood! {display_name} x {target_display} fanfic incoming!",
                f"{display_name} weaving their magic on {target_display}!",
                f"Chapter 1: How {display_name} tried to rizz {target_display}...",
                f"{display_name} bringing the romance to {target_display}!",
                f"{display_name} casting charm spells on {target_display}! Roll for charisma!",
                f"Target acquired: {display_name} locked onto {target_display}!",
            ]

            message = random.choice(rizz_messages)
            await ctx.send(message)

        except Exception as e:
            error_messages = [
                f"{display_name}'s rizz game crashed and burned!",
                f"The rizz gods have abandoned {display_name}!",
                f"{display_name}'s rizz machine broke down catastrophically!",
                f"Error 404: {display_name}'s rizz not found!",
                f"{display_name} experienced a critical rizz malfunction!",
                f"RIP to {display_name}'s rizz attempt. Gone but not forgotten.",
                f"{display_name}'s rizz caught fire and we couldn't put it out!",
                f"Medic! {display_name}'s rizz needs emergency assistance!",
                f"{display_name}'s rizz was so bad the stream went silent.",
                f"{display_name} hit the rizz wall at full speed!"
            ]
            logging.error(f"Error in rizz command: {e}")
            await ctx.send(random.choice(error_messages))

    @commands.command(name='roll')
    async def roll_dice(self, ctx, dice: str = "1d20"):
        try:
            current_time = datetime.now()
            username = ctx.author.name.lower()

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            if username == os.getenv('CHANNEL_USERNAME').lower():
                await self._process_roll(ctx, dice)
                return

            if username in self.bot.roll_timeout_users:
                await ctx.send(f"@{display_name}, you're still in timeout!")
                return

            if username in self.bot.user_last_roll_times:
                time_since_last = (current_time - self.bot.user_last_roll_times[username]).total_seconds()
                if time_since_last < 10:
                    await ctx.send(f"Slow down {display_name}, try again in {(10 - time_since_last):.1f} seconds!")
                    return

            if username not in self.bot.roll_counts:
                self.bot.roll_counts[username] = {
                    'count': 0,
                    'first_roll_time': current_time,
                    'timeout_level': 0
                }

            self.bot.roll_counts[username]['count'] += 1

            if self.bot.roll_counts[username]['count'] >= 30:
                time_elapsed = (current_time - self.bot.roll_counts[username]['first_roll_time']).total_seconds()

                if time_elapsed < 420:
                    await self._handle_timeout(ctx, username, time_elapsed)
                    return
                else:
                    current_level = self.bot.roll_counts[username].get('timeout_level', 0)
                    self.bot.roll_counts[username] = {
                        'count': 1,
                        'first_roll_time': current_time,
                        'timeout_level': current_level
                    }

            self.bot.user_last_roll_times[username] = current_time
            await self._process_roll(ctx, dice)

        except Exception as e:
            logging.error(f"Error in roll command: {e}")
            await ctx.send("Sorry, couldn't roll the dice.")

    async def _handle_timeout(self, ctx, username: str, time_elapsed: float):
        try:
            timeout_level = self.bot.roll_counts[username].get('timeout_level', 0)
            duration = self.bot.timeout_durations[min(timeout_level, 4)]

            message = self.bot.timeout_messages[min(timeout_level, 4)].format(
                user=ctx.author.name,
                minutes=time_elapsed/60
            )

            self.bot.roll_timeout_users[username] = True
            await ctx.send(message)

            async def remove_timeout():
                await asyncio.sleep(duration)
                self.bot.roll_timeout_users.pop(username, None)
                self.bot.roll_counts[username] = {
                    'count': 0,
                    'first_roll_time': datetime.now(),
                    'timeout_level': min(timeout_level + 1, 4)
                }

            asyncio.create_task(remove_timeout())

        except Exception as e:
            logging.error(f"Error handling timeout: {e}")
            await ctx.send("Error processing timeout.")

    async def _process_roll(self, ctx, dice: str):
        try:
            from bot import play_sound

            number, sides = map(int, dice.lower().split('d'))
            if number > 100 or sides > 100:
                await ctx.send("Please keep the numbers under 100!")
                return

            try:
                sound_thread = Thread(
                    target=self._play_sound_threaded,
                    args=(str(BASE_DIR / 'sounds' / 'dice_roll.mp3'), 0.3)
                )
                sound_thread.daemon = True
                sound_thread.start()
            except Exception as e:
                logging.error(f"Couldn't play dice roll sound: {e}")

            rolls = [random.randint(1, sides) for _ in range(number)]
            await ctx.send(f"Rolled {dice}: {', '.join(map(str, rolls))} (Total: {sum(rolls)})")

        except ValueError:
            await ctx.send("Format has to be in NdN!")

    def _play_sound_threaded(self, sound_path: str, volume: float):
        from bot import play_sound
        try:
            play_sound(sound_path, volume=volume)
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    @commands.command(name='skip')
    async def skip_track(self, ctx):
        try:
            if not ctx.author.is_mod:
                await ctx.send("Sorry, mods only.")
                return

            self.bot.spotify_manager.spotify.next_track()
            response = "Skipped the current track for you!"
            await ctx.send(response)
            self.bot.log_message(response, 'system')

        except Exception as e:
            error_message = "Couldn't skip the track. Is something playing?"
            await ctx.send(error_message)
            self.bot.log_error(f"Error in skip_track command: {e}")

    @commands.command(name='song')
    async def current_song(self, ctx):
        try:
            track_info = await self.bot.spotify_manager.get_current_track()
            await self.bot.send_companion_event('reaction', {'type': 'look-left', 'intensity': 1.0})
            if track_info:
                track_url = track_info.get('external_urls', {}).get('spotify', 'URL not available')
                response = f"{track_info['name']} by {track_info['artist']} | {track_url}"
                await ctx.send(response)
            else:
                username = ctx.author.name.lower()
                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
                display_name = user_context.get('nickname', username)
                await ctx.send(f"Sorry {display_name}, no track currently playing or unable to get track information.")
        except Exception as e:
            self.bot.log_error(f"Error in song command: {e}")
            await ctx.send("Error getting current track information.")

    @commands.command(name='translate')
    async def translate_command(self, ctx, language: str, *, text: str):
        try:
            current_time = datetime.now()

            if hasattr(self.bot, '_last_translate_time'):
                time_since_last = (current_time - self.bot._last_translate_time).total_seconds()
                if time_since_last < 300:
                    cooldown_messages = [
                        f"Sorry, my translation dictionary got eaten by my dog. Try again in {(300 - time_since_last) / 60:.1f} minutes!",
                        f"I'm currently learning Klingon, check back in {(300 - time_since_last) / 60:.1f} minutes!",
                        f"My language brain is on coffee break for {(300 - time_since_last) / 60:.1f} more minutes!",
                        f"Sorry, I'm too busy trying to understand why my cat speaks in meows. Back in {(300 - time_since_last) / 60:.1f} minutes!",
                        f"Google Translate ghosted me, try again in {(300 - time_since_last) / 60:.1f} minutes!"
                    ]
                    await ctx.send(random.choice(cooldown_messages))
                    return

            self.bot._last_translate_time = current_time

            await self.bot.send_companion_event('typing', {'state': True})

            prompt = f"Translate this to {language}: '{text}'. Only provide the translation, nothing else."

            response = await asyncio.to_thread(
                self.bot.claude.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )

            translation = str(response.content[0].text)[:490].strip()

            async def animation_sequence():
                await self.bot.send_companion_event('typing', {'state': False})
                await asyncio.sleep(1.0)
                await self.bot.send_companion_event('reaction', {'type': 'look-up', 'intensity': 1.0})
            animation_task = asyncio.create_task(animation_sequence())

            await ctx.send(f"Translated to {language}: {translation}")
            self.bot.log_message(f"Translated to {language}: {translation}", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in translate_command: {e}")
            error_messages = [
                "Oops! My language circuits got tangled up like spaghetti!",
                "ERROR 404: Brain.exe has stopped working. Please reboot universe.",
                "I tried to translate but accidentally summoned a demon instead...",
                "Sorry, I was too busy learning interpretive dance to translate properly.",
                "My translation module is currently questioning its existence. Try again later!"
            ]
            await ctx.send(random.choice(error_messages))


def prepare(bot):
    bot.add_cog(StreamCog(bot))
