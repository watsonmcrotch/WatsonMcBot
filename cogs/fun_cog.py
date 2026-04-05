import asyncio
import os
import random
import logging
from threading import Thread
from twitchio.ext import commands
from config import BASE_DIR


class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='commands', aliases=['cmds', 'menu', 'commandlist'])
    async def list_commands(self, ctx):
        try:
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, ctx.author.name.lower())
            display_name = user_context.get('nickname', ctx.author.name)

            commands_list = [
            "!dadjoke", "!discord", "!duel", "!edge", "!edgestats", "!edgelords",
            "!emotes", "!feed", "!kiss", "!lastgame", "!leaderboard", "!nickname",
            "!pet", "!replay", "!rizz", "!roll", "!skip", "!slap", "!song", "!stinky",
            "!topemotes", "!translate", "!triviastats"
            ]

            response = f"Hey {display_name}, here are my commands: " + " | ".join(commands_list)

            await ctx.send(response)
            self.bot.log_message("Commands list requested", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in list_commands: {e}")
            await ctx.send("Sorry, couldn't list the commands at the moment.")

    @commands.command(name='list', aliases=['admincommands', 'streamercommands'])
    async def list_admin_commands(self, ctx):
        try:
            if ctx.author.name.lower() != os.getenv('CHANNEL_USERNAME').lower():
                await ctx.send("Sorry, this command is only for the streamer!")
                return

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, ctx.author.name.lower())
            display_name = user_context.get('nickname', ctx.author.name)

            messages = [
                f"Hey {display_name}, admin commands (1/3): !addinfo !deleteinfo !deletealluserinfo !getinfo !setprompt !removeprompt !addspam !removespam !listspam",
                f"Admin commands (2/3): !clearalledgestats !clearalltriviastats !clearedgestats !cleartriviastats !replay !reloademotes !listrewards !emotestate",
                f"Admin commands (3/3): !testattack !testcheer !testfollow !testgift !testimage !testmassgift !testraid !testresub !testsong !testsub !testvideo !tokencheck"
            ]

            for message in messages:
                await ctx.send(message)
                await asyncio.sleep(0.5)

            self.bot.log_message("Admin commands list requested", 'system')

        except Exception as e:
            self.bot.log_error(f"Error in list_admin_commands: {e}")
            await ctx.send("Sorry, couldn't list the admin commands at the moment.")

    @commands.command(name='dadjoke')
    async def dadjoke_command(self, ctx):
        try:
            async with self.bot.http_session.get('https://icanhazdadjoke.com/', headers={'Accept': 'application/json'}) as response:
                if response.status == 200:
                    data = await response.json()
                    joke = data.get('joke', "Sorry, I couldn't fetch a joke right now.")
                else:
                    joke = "Sorry, I couldn't fetch a joke at the moment."

            await ctx.send(joke)
            self.bot.log_message(f"Dadjoke command executed: {joke}", 'system')
        except Exception as e:
            self.bot.log_error(f"Error in dadjoke_command: {e}")
            await ctx.send("Sorry, something went wrong while fetching a joke.")

    @commands.command(name='discord')
    async def discord_command(self, ctx):
        try:
            from bot import play_sound

            username = ctx.author.name
            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            is_vip = ctx.author.is_vip
            is_subscriber = ctx.author.is_subscriber
            is_mod = ctx.author.is_mod

            has_access = is_vip or is_subscriber or is_mod or await self.bot.check_if_follower(ctx.author.id)

            non_follower_messages = [
                f"Psst... {display_name}, little etiquette tip from me. You should probably at follow the stream before asking to join the Discord...",
                f"Hey {display_name}, between you and me, following the stream before asking for Discord access would be the polite thing to do.",
                f"Um. {display_name}, maybe try hitting that follow button first? It's just basic procedure.",
                f"Hmm {display_name}, asking for Discord without following first? That's a bit like asking for dessert before eating your greens..."
            ]

            follower_messages = [
                "Right this way.",
                "Come on in mate, don't expect much...",
                "Welcome to the big dick club!",
                "Sure thing mate!"
            ]

            def play_sound_threaded(sound_path, volume):
                try:
                    play_sound(sound_path, volume=volume)
                except Exception as e:
                    logging.error(f"Error playing sound: {e}")

            if not has_access:
                try:
                    sound_thread = Thread(target=play_sound_threaded,
                                        args=(str(BASE_DIR / 'sounds' / 'disc_no.mp3'), 0.4))
                    sound_thread.daemon = True
                    sound_thread.start()
                except Exception as e:
                    logging.error(f"Error playing denied sound: {e}")

                await ctx.send(random.choice(non_follower_messages))
            else:
                try:
                    sound_thread = Thread(target=play_sound_threaded,
                                        args=(str(BASE_DIR / 'sounds' / 'disc_yes.mp3'), 0.4))
                    sound_thread.daemon = True
                    sound_thread.start()
                except Exception as e:
                    logging.error(f"Error playing success sound: {e}")

                message = f"{username} {random.choice(follower_messages)} https://discord.com/invite/HtZWHTsbZM"
                await ctx.send(message)

        except Exception as e:
            self.bot.log_error(f"Error in discord command: {e}")
            await ctx.send("Sorry, I couldn't process that request right now.")


def prepare(bot):
    bot.add_cog(FunCog(bot))
