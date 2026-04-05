import asyncio
import os
import logging
from twitchio.ext import commands
from models import EdgeStreak, TriviaStats, TriviaGame, TriviaRound


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='addinfo')
    async def add_custom_info(self, ctx, username: str, attribute: str, *, value: str):
        try:
            if ctx.author.name.lower() != self.bot.streamer_name.lower():
                await ctx.send("Sorry, only the streamer can add custom info!")
                return

            username = username.lower()
            attribute = attribute.lower()

            await asyncio.to_thread(self.bot.db_manager.add_custom_info, username, {attribute: value})

            response = f"Updated info for {username}. {attribute} = '{value}'"
            await ctx.send(response)
            self.bot.log_message(f"Updated {attribute} for {username} by {ctx.author.name}", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in add_custom_info command: {e}")
            await ctx.send("Sorry, I couldn't add the custom info at the moment.")

    @commands.command(name='addspam')
    async def add_spam_pattern(self, ctx, *, pattern: str):
        if ctx.author.name.lower() != self.bot.streamer_name.lower() and not ctx.author.is_mod:
            await ctx.send("Sorry, only the streamer can manage spam patterns.")
            return

        pattern = pattern.strip().lower()
        if pattern in self.bot.spam_patterns:
            await ctx.send(f"Pattern '{pattern}' is already in the spam detection list.")
            return

        self.bot.spam_patterns.append(pattern)
        await ctx.send(f"Added '{pattern}' to spam detection list. Current patterns: {', '.join(self.bot.spam_patterns)}")
        self.bot.log_message(f"Added spam pattern: {pattern}", 'system')

    @commands.command(name='clearalledgestats')
    async def clear_all_edge_stats(self, ctx):
        if ctx.author.name.lower() != self.bot.streamer_name.lower():
            await ctx.send("Sorry, only the streamer can clear stats!")
            return

        session = await asyncio.to_thread(self.bot.db_manager.get_session)
        try:
            count = await asyncio.to_thread(lambda: session.query(EdgeStreak).count())
            await asyncio.to_thread(lambda: session.query(EdgeStreak).delete())
            await asyncio.to_thread(session.commit)
            await ctx.send(f"Cleared {count} edge stats records!")

            self.bot.edge_streaks = {}
            self.bot.edge_milestones = {}
            self.bot.user_last_edge_times = {}
            self.bot.edge_session_starts = {}

        except Exception as e:
            session.rollback()
            logging.error(f"Error clearing edge stats: {e}")
            await ctx.send("Error clearing edge stats!")
        finally:
            session.close()

    @commands.command(name='clearalltriviastats')
    async def clear_all_trivia_stats(self, ctx):
        try:
            if not ctx.author.is_broadcaster:
                await ctx.send(f"@{ctx.author.name}, only the streamer can clear all trivia stats!")
                return

            session = await asyncio.to_thread(self.bot.db_manager.get_session)
            try:
                stats_count = await asyncio.to_thread(lambda: session.query(TriviaStats).count())
                games_count = await asyncio.to_thread(lambda: session.query(TriviaGame).count())
                rounds_count = await asyncio.to_thread(lambda: session.query(TriviaRound).count())

                await asyncio.to_thread(lambda: session.query(TriviaRound).delete())
                await asyncio.to_thread(lambda: session.query(TriviaGame).delete())
                await asyncio.to_thread(lambda: session.query(TriviaStats).delete())
                await asyncio.to_thread(session.commit)

                await ctx.send(f"All trivia stats cleared! Removed {stats_count} player stats, {games_count} games, and {rounds_count} rounds.")
                logging.info(f"All trivia stats cleared by broadcaster {ctx.author.name}")

            except Exception as e:
                session.rollback()
                logging.error(f"Error clearing all trivia stats: {e}")
                await ctx.send("Error clearing trivia stats.")

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Unexpected error in clear_all_trivia_stats: {e}")
            await ctx.send("An unexpected error occurred when clearing trivia stats.")

    @commands.command(name='clearedgestats')
    async def clear_user_edge_stats(self, ctx, username: str = None):
        if ctx.author.name.lower() != self.bot.streamer_name.lower():
            await ctx.send("Sorry, only the streamer can clear stats!")
            return

        if not username:
            await ctx.send("Please specify a username to clear!")
            return

        session = await asyncio.to_thread(self.bot.db_manager.get_session)
        try:
            stats = await asyncio.to_thread(
                lambda: session.query(EdgeStreak).filter_by(username=username.lower()).first()
            )
            if stats:
                await asyncio.to_thread(session.delete, stats)
                await asyncio.to_thread(session.commit)

                if username in self.bot.edge_streaks:
                    del self.bot.edge_streaks[username]
                if username in self.bot.edge_milestones:
                    del self.bot.edge_milestones[username]
                if username in self.bot.user_last_edge_times:
                    del self.bot.user_last_edge_times[username]
                if username in self.bot.edge_session_starts:
                    del self.bot.edge_session_starts[username]

                await ctx.send(f"Cleared edge stats for {username}!")
            else:
                await ctx.send(f"No edge stats found for {username}!")

        except Exception as e:
            session.rollback()
            logging.error(f"Error clearing user edge stats: {e}")
            await ctx.send(f"Error clearing stats for {username}!")
        finally:
            session.close()

    @commands.command(name='cleartriviastats')
    async def clear_trivia_stats(self, ctx, username: str = None):
        try:
            if not ctx.author.is_broadcaster:
                await ctx.send(f"@{ctx.author.name}, only the streamer can clear trivia stats!")
                return

            if not username:
                await ctx.send("Please specify a username to clear stats for!")
                return

            target_user = username.lower()
            session = await asyncio.to_thread(self.bot.db_manager.get_session)

            try:
                stats = await asyncio.to_thread(
                    lambda: session.query(TriviaStats).filter_by(username=target_user).first()
                )
                if not stats:
                    await ctx.send(f"No trivia stats found for {username}!")
                    return

                await asyncio.to_thread(session.delete, stats)
                await asyncio.to_thread(session.commit)

                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
                display_name = user_context.get('nickname', target_user)

                await ctx.send(f"Trivia stats cleared for {display_name}!")

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error in clear_trivia_stats: {e}")
            await ctx.send("Couldn't clear trivia stats right now!")

    @commands.command(name='deletealluserinfo')
    async def delete_all_user_info(self, ctx, username: str):
        try:
            if ctx.author.name.lower() != self.bot.streamer_name.lower():
                await ctx.send("Sorry, only the streamer can delete all a user's info!")
                return

            username = username.lower()
            count = await asyncio.to_thread(self.bot.db_manager.delete_all_info, username)

            if count > 0:
                response = f"Deleted all custom info for {username} ({count} total attributes removed)"
                await ctx.send(response)
                self.bot.log_message(f"Deleted all info for {username} by {ctx.author.name}", 'system')
            else:
                response = f"No custom info found for {username}"
                await ctx.send(response)
                self.bot.log_message(response, 'system')

        except Exception as e:
            self.bot.log_error(f"Error in delete_all_user_info command: {e}")
            await ctx.send("Sorry, I couldn't delete the custom info at the moment.")

    @commands.command(name='deleteinfo')
    async def delete_specific_info(self, ctx, username: str, attribute: str):
        try:
            if ctx.author.name.lower() != self.bot.streamer_name.lower():
                await ctx.send("Sorry, only the streamer can delete an attribute!")
                return

            username = username.lower()
            attribute = attribute.lower()

            success = await asyncio.to_thread(self.bot.db_manager.delete_specific_info, username, attribute)

            if success:
                response = f"Deleted {attribute} for {username}"
                await ctx.send(response)
                self.bot.log_message(f"Deleted {attribute} info for {username} by {ctx.author.name}", 'system')
            else:
                response = f"No {attribute} found for {username}"
                await ctx.send(response)
                self.bot.log_message(response, 'system')

        except Exception as e:
            self.bot.log_error(f"Error in delete_specific_info command: {e}")
            await ctx.send("Sorry, I couldn't delete the custom info at the moment.")

    @commands.command(name='getinfo')
    async def get_custom_info(self, ctx, username: str):
        try:
            if ctx.author.name.lower() != self.bot.streamer_name.lower():
                await ctx.send("Sorry, only the streamer retrieve user info!")
                return

            username = username.lower()
            user_data = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            custom_info = user_data.get('custom_info', {})

            if custom_info:
                info_lines = [f"{key}: {value}" for key, value in custom_info.items()]
                info_message = " | ".join(info_lines)
                response = f"Info for {username}: {info_message}"
                await ctx.send(response)
                self.bot.log_message(response, 'system')
            else:
                response = f"No custom info found for {username}"
                await ctx.send(response)
                self.bot.log_message(response, 'system')
        except Exception as e:
            self.bot.log_error(f"Error in get_custom_info command: {e}")
            await ctx.send("Sorry, I couldn't retrieve the custom info at the moment.")

    @commands.command(name='listrewards', aliases=['channelpointids', 'redeemids'])
    async def list_rewards(self, ctx):
        if ctx.author.name.lower() != self.bot.streamer_name.lower():
            await ctx.send("Sorry mate, that's a streamer only command.")
            return
        try:
            if not self.bot._channel_id:
                self.bot._channel_id = await self.bot.get_broadcaster_id()
                if not self.bot._channel_id:
                    await ctx.send("Failed to get broadcaster ID!")
                    return

            self.bot.log_message(f"Channel ID: {self.bot._channel_id}")
            self.bot.log_message(f"Broadcaster Client ID: {self.bot.broadcaster_client_id}")
            self.bot.log_message(f"Token being used: {self.bot.broadcaster_token[:10]}...")

            headers = {
                'Client-ID': self.bot.broadcaster_client_id,
                'Authorization': f'Bearer {self.bot.broadcaster_token}'
            }

            async with self.bot.http_session.get(f'https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={self.bot._channel_id}', headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    rewards = data.get('data', [])
                    self.bot.log_message("Channel Point Rewards:", 'system')
                    for reward in rewards:
                        reward_info = f"""
                        Reward: {reward['title']}
                        ID: {reward['id']}
                        Cost: {reward['cost']} points
                        -----------------"""
                        self.bot.log_message(reward_info, 'system')
                    await ctx.send("Reward IDs have been logged to the console!")
                else:
                    error_data = await response.text()
                    self.bot.log_error(f"Error fetching rewards: {error_data}")
                    await ctx.send(f"Failed to fetch rewards. Status: {response.status}. Check the logs for details.")
        except Exception as e:
            self.bot.log_error(f"Error listing rewards: {e}")
            await ctx.send("An error occurred while fetching rewards.")

    @commands.command(name='listspam')
    async def list_spam_patterns(self, ctx):
        if ctx.author.name.lower() != self.bot.streamer_name.lower() and not ctx.author.is_mod:
            await ctx.send("Sorry, only the streamer can view spam patterns.")
            return

        if not self.bot.spam_patterns:
            await ctx.send("No spam patterns are currently configured.")
            return

        patterns_list = ", ".join(f"'{pattern}'" for pattern in self.bot.spam_patterns)
        await ctx.send(f"Current spam detection patterns: {patterns_list}")

    @commands.command(name='reloademotes')
    async def reload_emotes(self, ctx):
        try:
            if not ctx.author.is_mod:
                await ctx.send("Sorry, this command is for moderators only!")
                return

            seventv_user_id = os.getenv('SEVENTV_USER_ID')
            logging.info(f"7TV User ID: {seventv_user_id}")

            if not seventv_user_id:
                await ctx.send("Error: 7TV user ID not configured!")
                return

            await ctx.send("Reloading emotes, please wait...")

            old_emotes = set(self.bot.emote_tracker.seventv_emotes.keys())
            current_usage = dict(self.bot.emote_tracker.emote_usage)

            await self.bot.emote_tracker.load_7tv_emotes(seventv_user_id, http_session=self.bot.http_session)

            new_emotes = set(self.bot.emote_tracker.seventv_emotes.keys())
            added = new_emotes - old_emotes
            removed = old_emotes - new_emotes

            self.bot.emote_tracker.emote_usage = current_usage

            if added or removed:
                changes = []
                if added:
                    changes.append(f"Added: {', '.join(added)}")
                if removed:
                    changes.append(f"Removed: {', '.join(removed)}")
                await ctx.send(f"Reloaded {len(self.bot.emote_tracker.seventv_emotes)} emotes! Changes: {' | '.join(changes)}")
            else:
                await ctx.send(f"Reloaded {len(self.bot.emote_tracker.seventv_emotes)} emotes! No changes detected.")

        except Exception as e:
            logging.error(f"Error in reload_emotes command: {e}")
            await ctx.send("Sorry, something went wrong while reloading emotes.")

    @commands.command(name='removespam')
    async def remove_spam_pattern(self, ctx, *, pattern: str):
        if ctx.author.name.lower() != self.bot.streamer_name.lower() and not ctx.author.is_mod:
            await ctx.send("Sorry, only the streamer can manage spam patterns.")
            return

        pattern = pattern.strip().lower()
        if pattern not in self.bot.spam_patterns:
            await ctx.send(f"Pattern '{pattern}' is not in the spam detection list.")
            return

        self.bot.spam_patterns.remove(pattern)
        await ctx.send(f"Removed '{pattern}' from spam detection list. Current patterns: {', '.join(self.bot.spam_patterns)}")
        self.bot.log_message(f"Removed spam pattern: {pattern}", 'system')


def prepare(bot):
    bot.add_cog(AdminCog(bot))
