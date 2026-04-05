import asyncio
import os
import uuid
import logging
from datetime import datetime
from twitchio.ext import commands


class AdminTestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='emotestate')
    async def check_emote_state(self, ctx):
        if not ctx.author.is_mod:
            return
        state = {
            'loaded': self.bot.emote_tracker._emotes_loaded,
            'loading': self.bot.emote_tracker._loading,
            'count': len(self.bot.emote_tracker.seventv_emotes),
            'usage_records': len(self.bot.emote_tracker.emote_usage)
        }
        await ctx.send(str(state))

    @commands.command(name='ping')
    async def ping(self, ctx):
        try:
            self.bot.log_message("Received ping command", 'system')
            await ctx.send('pong!')
            self.bot.log_message("Sent pong response", 'system')
        except Exception as e:
            self.bot.log_error(f"Error in ping command: {str(e)}")

    @commands.command(name='testattack')
    async def test_attack(self, ctx, amount: int = 10):
        if not ctx.author.is_mod:
            return

        try:
            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if not channel:
                return

            await ctx.send(f"Testing attack detection with {amount} follows...")

            self.bot.follow_detector.follow_queue.clear()

            for i in range(amount):
                test_follow = {
                    'user_id': f'test{i}',
                    'user_login': f'testbot_{i}',
                }
                self.bot.follow_detector.follow_queue.append(test_follow)

            self.bot.follow_detector.channel = channel
            await self.bot.follow_detector.activate_attack_mode(datetime.now())
            await self.bot.follow_detector.handle_attack_end()

        except Exception as e:
            self.bot.log_error(f"Error in test_attack: {e}")

    @commands.command(name='testcheer')
    async def test_cheer(self, ctx, bits_or_user: str = "100", bits: int = None, *, message: str = None):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        try:
            mock_username = None
            cheer_bits = 100

            if bits_or_user.isdigit():
                cheer_bits = int(bits_or_user)
            else:
                mock_username = bits_or_user.lower()
                if bits is not None:
                    cheer_bits = bits

            if mock_username:
                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, mock_username)
                display_name = user_context.get('nickname', mock_username)
            else:
                mock_username = ctx.author.name.lower()
                display_name = ctx.author.name

            mock_cheer_event = {
                'user_id': '12345',
                'user_login': mock_username,
                'user_name': display_name,
                'broadcaster_user_id': '147871546',
                'broadcaster_user_login': 'watsonmcrotch',
                'broadcaster_user_name': 'WatsonMcRotch',
                'bits': cheer_bits,
                'message': message or 'Test cheer message!'
            }

            await self.bot.handle_eventsub_notification('channel.cheer', mock_cheer_event)

        except Exception as e:
            self.bot.log_error(f"Error in test_cheer command: {e}")
            await ctx.send("Sorry, something went wrong testing the cheer alert!")

    @commands.command(name='testfollow')
    async def test_follow(self, ctx, username: str = None):
        if not ctx.author.is_mod:
            return

        try:
            if not username:
                await ctx.send("Usage: !testfollow [username]")
                return

            channel = self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))
            if not channel:
                return

            await ctx.send(f"Testing follow from {username}...")
            mock_follow = {
                'user_id': str(uuid.uuid4())[:8],
                'user_login': username,
                'user_name': username
            }

            is_attack = await self.bot.follow_detector.check_follow(mock_follow, channel)
            if not is_attack:
                await self.bot.follow_alert.trigger(mock_follow['user_login'])

        except Exception as e:
            self.bot.log_error(f"Error in test_follow: {e}")

    @commands.command(name='testgift')
    async def test_gift(self, ctx, recipient_or_amount: str = None):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        try:
            amount = int(recipient_or_amount)
            mock_gift_event = {
                'user_id': '12345',
                'user_login': ctx.author.name.lower(),
                'user_name': ctx.author.name,
                'broadcaster_user_id': '147871546',
                'broadcaster_user_login': 'watsonmcrotch',
                'broadcaster_user_name': 'WatsonMcRotch',
                'total': amount,
                'tier': '1000',
                'is_anonymous': False,
                'cumulative_total': amount
            }
            await self.bot.handle_eventsub_notification('channel.subscription.gift', mock_gift_event)
        except ValueError:
            if recipient_or_amount:
                mock_gift_event = {
                    'user_id': '12345',
                    'user_login': ctx.author.name.lower(),
                    'user_name': ctx.author.name,
                    'broadcaster_user_id': '147871546',
                    'broadcaster_user_login': 'watsonmcrotch',
                    'broadcaster_user_name': 'WatsonMcRotch',
                    'tier': '1000',
                    'is_gift': True,
                    'recipient_user_name': recipient_or_amount,
                    'recipient_user_login': recipient_or_amount.lower()
                }
                await self.bot.handle_eventsub_notification('channel.subscribe', mock_gift_event)
            else:
                await ctx.send("Usage: !testgift <username> or !testgift <number>")

    @commands.command(name='testimage')
    async def test_image(self, ctx, *, prompt: str = None):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        try:
            if not prompt:
                prompt = "A majestic castle on a floating island in a sunset sky, digital art style"

            username = ctx.author.name.lower()
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            user_color = user_context.get('color', '#FF69B4')

            original_channel_id = self.bot.image_redeem.discord_channel_id
            original_user_id = self.bot.discord_monitor.discord_user_id

            self.bot.image_redeem.discord_channel_id = None
            self.bot.discord_monitor.discord_user_id = int(os.getenv('DISCORD_TEST_USER_ID'))

            try:
                await self.bot.image_redeem.process_image_redeem(
                    channel=ctx.channel,
                    username=username,
                    prompt=prompt,
                    user_color=user_color
                )
            finally:
                self.bot.image_redeem.discord_channel_id = original_channel_id
                self.bot.discord_monitor.discord_user_id = original_user_id

        except Exception as e:
            self.bot.log_error(f"Error in test_image command: {e}")
            await ctx.send("Sorry, something went wrong testing the image redeem!")

    @commands.command(name='testvideo')
    async def test_video(self, ctx, *, prompt: str = None):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        try:
            if not prompt:
                prompt = "A serene mountain landscape with a flowing river at sunset"

            username = ctx.author.name.lower()
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            user_color = user_context.get('color', '#FF69B4')

            original_channel_id = self.bot.video_redeem.discord_channel_id
            original_user_id = self.bot.discord_monitor.discord_user_id

            self.bot.video_redeem.discord_channel_id = None
            self.bot.discord_monitor.discord_user_id = int(os.getenv('DISCORD_TEST_USER_ID'))

            try:
                await self.bot.video_redeem.process_video_redeem(
                    channel=ctx.channel,
                    username=username,
                    prompt=prompt,
                    user_color=user_color
                )
            finally:
                self.bot.video_redeem.discord_channel_id = original_channel_id
                self.bot.discord_monitor.discord_user_id = original_user_id

        except Exception as e:
            self.bot.log_error(f"Error in test_video command: {e}")
            await ctx.send("Sorry, something went wrong testing the video redeem!")

    @commands.command(name='testmassgift')
    async def test_mass_gift(self, ctx, amount: int = 5):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        mock_gift_event = {
            'user_id': '12345',
            'user_login': ctx.author.name.lower(),
            'user_name': ctx.author.name,
            'broadcaster_user_id': '147871546',
            'broadcaster_user_login': 'watsonmcrotch',
            'broadcaster_user_name': 'WatsonMcRotch',
            'total': amount,
            'tier': '1000',
            'is_anonymous': False,
            'cumulative_total': amount
        }
        await self.bot.handle_eventsub_notification('channel.subscription.gift', mock_gift_event)

    @commands.command(name='testraid')
    async def test_raid(self, ctx, username: str = None, viewers: int = None):
        if not ctx.author.is_mod:
            return

        try:
            if not username:
                await ctx.send("Usage: !testraid [username] [viewers]")
                return

            viewers = viewers or 100

            mock_raid_event = {
                'from_broadcaster_user_id': '12345',
                'from_broadcaster_user_login': username.lower(),
                'from_broadcaster_user_name': username,
                'to_broadcaster_user_id': self.bot._channel_id,
                'to_broadcaster_user_login': 'watsonmcrotch',
                'to_broadcaster_user_name': 'WatsonMcRotch',
                'viewers': viewers
            }

            await self.bot.handle_eventsub_notification('channel.raid', mock_raid_event)

        except Exception as e:
            self.bot.log_error(f"Error in test_raid: {e}")

    @commands.command(name='testresub')
    async def test_resub(self, ctx):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        mock_resub_event = {
            'user_id': '12345',
            'user_login': ctx.author.name.lower(),
            'user_name': ctx.author.name,
            'broadcaster_user_id': '147871546',
            'broadcaster_user_login': 'watsonmcrotch',
            'broadcaster_user_name': 'WatsonMcRotch',
            'tier': '1000',
            'message': {'text': 'Test resub message'},
            'cumulative_months': 3,
            'streak_months': 3,
            'duration_months': 1
        }

        await self.bot.handle_eventsub_notification('channel.subscription.message', mock_resub_event)

    @commands.command(name='testsong')
    async def test_song(self, ctx, *, prompt: str = None):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        try:
            if not prompt:
                prompt = "Generate an upbeat electronic dance song with heavy bass and synthesizers"

            username = ctx.author.name.lower()
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            user_color = user_context.get('color', '#FF69B4')

            original_channel_id = self.bot.music_redeem.discord_channel_id
            original_user_id = self.bot.discord_monitor.discord_user_id

            self.bot.music_redeem.discord_channel_id = None
            self.bot.discord_monitor.discord_user_id = int(os.getenv('DISCORD_TEST_USER_ID'))

            try:
                await self.bot.music_redeem.process_song_redeem(
                    channel=ctx.channel,
                    username=username,
                    prompt=prompt,
                    user_color=user_color
                )
            finally:
                self.bot.music_redeem.discord_channel_id = original_channel_id
                self.bot.discord_monitor.discord_user_id = original_user_id

        except Exception as e:
            self.bot.log_error(f"Error in test_song command: {e}")
            await ctx.send("Sorry, something went wrong testing the song redeem!")

    @commands.command(name='testsub')
    async def test_sub(self, ctx):
        if not ctx.author.is_mod:
            await ctx.send("Sorry, this is a moderator-only command!")
            return

        mock_sub_event = {
            'user_id': '12345',
            'user_login': ctx.author.name.lower(),
            'user_name': ctx.author.name,
            'broadcaster_user_id': '147871546',
            'broadcaster_user_login': 'watsonmcrotch',
            'broadcaster_user_name': 'WatsonMcRotch',
            'tier': '1000',
            'is_gift': False
        }

        await self.bot.handle_eventsub_notification('channel.subscribe', mock_sub_event)

    @commands.command(name='tokencheck')
    async def check_tokens(self, ctx):
        if not ctx.author.is_mod:
            return
        bot_valid = await self.bot.token_manager.validate_token('bot')
        broadcaster_valid = await self.bot.token_manager.validate_token('broadcaster')
        await ctx.send(f"Bot token valid: {bot_valid}, Broadcaster token valid: {broadcaster_valid}")


def prepare(bot):
    bot.add_cog(AdminTestCog(bot))
