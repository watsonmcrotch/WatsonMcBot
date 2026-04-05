import time
import logging
from twitchio.ext import commands


class CompanionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_pet_time = {}
        self._last_feed_time = {}
        self._last_slap_time = {}
        self._last_kiss_time = {}
        self._last_tickle_time = {}
        self._last_scare_time = {}
        self._last_dance_time = {}
        self._last_hug_time = {}
        self._last_bonk_time = {}

    @commands.command(name='pet')
    async def pet_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_pet_time:
                if current_time - self._last_pet_time[username] < 30:
                    return
            self._last_pet_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'pet', 'intensity': 1.0})
        except Exception as e:
            self.bot.log_error(f"Error in pet_companion: {e}")

    @commands.command(name='feed')
    async def feed_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_feed_time:
                if current_time - self._last_feed_time[username] < 45:
                    return
            self._last_feed_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'feed', 'intensity': 1.0})
        except Exception as e:
            self.bot.log_error(f"Error in feed_companion: {e}")

    @commands.command(name='slap')
    async def slap_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_slap_time:
                if current_time - self._last_slap_time[username] < 60:
                    return
            self._last_slap_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'slap', 'intensity': 1.2})
        except Exception as e:
            self.bot.log_error(f"Error in slap_companion: {e}")

    @commands.command(name='kiss')
    async def kiss_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_kiss_time:
                if current_time - self._last_kiss_time[username] < 60:
                    return
            self._last_kiss_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'kiss', 'intensity': 1.5})
        except Exception as e:
            self.bot.log_error(f"Error in kiss_companion: {e}")

    @commands.command(name='tickle')
    async def tickle_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_tickle_time:
                if current_time - self._last_tickle_time[username] < 30:
                    return
            self._last_tickle_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'tickle', 'intensity': 1.0})
        except Exception as e:
            self.bot.log_error(f"Error in tickle_companion: {e}")

    @commands.command(name='scare')
    async def scare_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_scare_time:
                if current_time - self._last_scare_time[username] < 60:
                    return
            self._last_scare_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'scare', 'intensity': 1.2})
        except Exception as e:
            self.bot.log_error(f"Error in scare_companion: {e}")

    @commands.command(name='dance')
    async def dance_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_dance_time:
                if current_time - self._last_dance_time[username] < 30:
                    return
            self._last_dance_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'dance', 'intensity': 1.0})
        except Exception as e:
            self.bot.log_error(f"Error in dance_companion: {e}")

    @commands.command(name='hug')
    async def hug_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_hug_time:
                if current_time - self._last_hug_time[username] < 30:
                    return
            self._last_hug_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'hug', 'intensity': 1.0})
        except Exception as e:
            self.bot.log_error(f"Error in hug_companion: {e}")

    @commands.command(name='bonk')
    async def bonk_companion(self, ctx):
        try:
            current_time = time.time()
            username = ctx.author.name.lower()
            if username in self._last_bonk_time:
                if current_time - self._last_bonk_time[username] < 60:
                    return
            self._last_bonk_time[username] = current_time
            await self.bot.send_companion_event('reaction', {'type': 'bonk', 'intensity': 1.2})
        except Exception as e:
            self.bot.log_error(f"Error in bonk_companion: {e}")


def prepare(bot):
    bot.add_cog(CompanionCog(bot))
