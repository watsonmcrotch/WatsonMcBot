import asyncio
import os
import logging
from twitchio.ext import commands


class OverlayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_mod(self, ctx):
        return ctx.author.is_mod or ctx.author.name.lower() == os.getenv('CHANNEL_USERNAME', '').lower()

    def _get_channel(self):
        return self.bot.get_channel(os.getenv('CHANNEL_USERNAME'))

    @commands.command(name='effect')
    async def effect_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_effect(channel, ctx.author.name, args, is_mod))

    @commands.command(name='errors')
    async def errors_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_errors(channel, ctx.author.name, args, is_mod))

    @commands.command(name='tbc')
    async def tbc_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_tbc(channel, ctx.author.name, args, is_mod))

    @commands.command(name='maze')
    async def maze_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_maze(channel, ctx.author.name, args, is_mod))

    @commands.command(name='clippy')
    async def clippy_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_clippy(channel, ctx.author.name, args, is_mod))

    @commands.command(name='desktop')
    async def desktop_command(self, ctx):
        is_mod = self._is_mod(ctx)
        args = ctx.message.content.split()[1:]
        channel = self._get_channel()
        if channel:
            asyncio.create_task(self.bot.overlay_redeems.cmd_desktop(channel, ctx.author.name, args, is_mod))


def prepare(bot):
    bot.add_cog(OverlayCog(bot))
