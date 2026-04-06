import asyncio
import os
import random
import logging
from datetime import datetime, timedelta
from threading import Thread
from twitchio.ext import commands
from models import EdgeStreak
from config import BASE_DIR


class EdgeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _play_sound_threaded(self, sound_path, volume):
        from bot import play_sound
        try:
            play_sound(sound_path, volume=volume)
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    @commands.command(name='edge', aliases=['edge1', 'edge2', 'edge3', 'edge4', 'edge5', 'edge6', 'edge7', 'edge8', 'edge9', 'edge10'])
    async def edge_streak(self, ctx, attempts: str = "1"):
        asyncio.create_task(self._process_edge_command(ctx, attempts))

    async def _process_edge_command(self, ctx, attempts: str = "1"):
        try:
            from bot import play_sound

            command_name = ctx.message.content.split()[0][1:]

            if command_name.startswith('edge') and len(command_name) > 4:
                try:
                    attempts = command_name[4:]
                except Exception:
                    attempts = "1"

            try:
                num_attempts = min(int(attempts), 10)
                if num_attempts < 1:
                    num_attempts = 1
            except ValueError:
                num_attempts = 1

            current_time = datetime.now()
            username = ctx.author.name.lower()

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, username)
            display_name = user_context.get('nickname', username)

            if hasattr(self.bot, 'active_duels') and username in self.bot.active_duels:
                duel = self.bot.active_duels[username]
                challenger = list(self.bot.active_duels.keys())[0]
                opponent = duel['opponent']

                if duel['current_turn'] != username:
                    other_player = challenger if username == opponent else opponent
                    other_display = duel['challenger_display'] if username == opponent else duel['opponent_display']
                    await ctx.send(f"Wait your turn! It's {other_display}'s turn to edge!")
                    return

            if hasattr(self.bot, 'recovery_cooldowns') and username in self.bot.recovery_cooldowns:
                recovery_end = self.bot.recovery_cooldowns[username]
                if current_time < recovery_end:
                    remaining = (recovery_end - current_time).total_seconds()
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    await ctx.send(f"{display_name} you're spent! You need {minutes}m {seconds}s more recovery time...")
                    return

            in_active_duel = hasattr(self.bot, 'active_duels') and username in self.bot.active_duels

            if username in self.bot.user_last_edge_times and not in_active_duel:
                base_cooldown = 5
                attempt_multiplier = max(1, num_attempts / 2)
                total_cooldown = base_cooldown * attempt_multiplier

                time_since_last = (current_time - self.bot.user_last_edge_times[username]).total_seconds()
                if time_since_last < total_cooldown and username != os.getenv('CHANNEL_USERNAME').lower():
                    await ctx.send(f"Slow down {display_name}... {(total_cooldown - time_since_last):.1f} seconds...")
                    return

            if not hasattr(self.bot, 'edge_streaks'):
                self.bot.edge_streaks = {}
            if not hasattr(self.bot, 'edge_milestones'):
                self.bot.edge_milestones = {}
            if not hasattr(self.bot, 'recovery_cooldowns'):
                self.bot.recovery_cooldowns = {}
            if not hasattr(self.bot, 'active_blessings'):
                self.bot.active_blessings = {}

            def get_edge_stats():
                session = self.bot.db_manager.get_session()
                try:
                    stats = session.query(EdgeStreak).filter_by(username=username.lower()).first()
                    if not stats:
                        stats = EdgeStreak(
                            username=username.lower(),
                            highest_streak=0,
                            total_busts=0,
                            last_streak=0,
                            total_edges=0,
                            longest_session=0,
                            current_streak=0,
                            session_start=datetime.now()
                        )
                        session.add(stats)
                        session.commit()
                    elif not stats.session_start:
                        stats.session_start = datetime.now()
                        stats.current_streak = 0
                        session.commit()
                    return stats.current_streak, stats.highest_streak
                finally:
                    session.close()

            current_streak, highest_streak = await asyncio.to_thread(get_edge_stats)

            if username not in self.bot.edge_streaks:
                self.bot.edge_streaks[username] = current_streak
                self.bot.edge_milestones[username] = set()

            streak = self.bot.edge_streaks[username]
            success_count = 0
            messages = []
            old_pb = highest_streak

            session = await asyncio.to_thread(self.bot.db_manager.get_session)
            try:
                stats = await asyncio.to_thread(
                    lambda: session.query(EdgeStreak).filter_by(username=username.lower()).first()
                )

                if random.random() < 0.02 and username not in self.bot.active_blessings:
                    self.bot.active_blessings[username] = current_time + timedelta(minutes=15)
                    try:
                        sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'blessing.mp3'), 0.8))
                        sound_thread.daemon = True
                        sound_thread.start()
                    except Exception as e:
                        logging.error(f"Error playing blessing sound: {e}")
                    messages.append(f"Prayge The Edge Lord has blessed {display_name}! No recovery time for 15 minutes! Prayge")

                for i in range(num_attempts):
                    if streak <= 10:
                        bust_chance = 0.03 * (1 + (i * 0.1))
                    else:
                        base = 0.02
                        streak_past_10 = streak - 10
                        bust_chance = (base + (streak_past_10 * 0.00036) + pow(streak_past_10/250, 3)) * (1 + (i * 0.1))
                        bust_chance = min(bust_chance, 0.93)

                    if random.random() < bust_chance:
                        if success_count > 0:
                            messages.append(f"Made it through {success_count} edges before...")

                        if hasattr(self.bot, 'active_duels') and username in self.bot.active_duels:
                            duel = self.bot.active_duels[username]
                            challenger = list(self.bot.active_duels.keys())[0]
                            opponent = duel['opponent']
                            winner = opponent if username == challenger else challenger
                            winner_display = duel['opponent_display'] if username == challenger else duel['challenger_display']

                            stats.total_busts += 1
                            stats.last_streak = streak
                            stats.current_streak = 0
                            stats.session_start = None
                            await asyncio.to_thread(session.commit)

                            try:
                                if streak < 10:
                                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'sadtrombone.mp3'), 0.4))
                                elif streak >= 100:
                                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'megabust.mp3'), 0.8))
                                elif streak >= 50:
                                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'bigbust.mp3'), 0.6))
                                elif streak >= 10:
                                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'bust.mp3'), 0.5))

                                sound_thread.daemon = True
                                sound_thread.start()
                            except Exception as e:
                                logging.error(f"Error playing bust sound in duel: {e}")

                            await ctx.send(
                                f"{display_name} BUSTED at {streak}! "
                                f"{winner_display} wins the edge-off! "
                                f"{display_name} is a LOSER!"
                            )

                            if 'suspended_cooldowns' in duel and winner in duel['suspended_cooldowns']:
                                if not hasattr(self.bot, 'recovery_cooldowns'):
                                    self.bot.recovery_cooldowns = {}
                                self.bot.recovery_cooldowns[winner] = duel['suspended_cooldowns'][winner]

                            self.bot.last_duel_winner = {
                                'winner': winner_display,
                                'loser': display_name,
                                'streak': streak
                            }

                            del self.bot.active_duels[challenger]
                            del self.bot.active_duels[opponent]

                            self.bot.edge_streaks[username] = 0
                            self.bot.edge_streaks[winner] = 0
                            self.bot.edge_milestones[username] = set()
                            self.bot.edge_milestones[winner] = set()
                            return

                        recovery_mins = self._calculate_recovery_time(streak, username)
                        self.bot.recovery_cooldowns[username] = current_time + timedelta(minutes=recovery_mins)

                        stats.total_busts += 1
                        stats.last_streak = streak
                        stats.current_streak = 0
                        stats.session_start = None
                        await asyncio.to_thread(session.commit)

                        await self._handle_bust(ctx, display_name, streak, stats, recovery_mins)
                        self.bot.edge_streaks[username] = 0
                        self.bot.edge_milestones[username] = set()
                        return

                    success_count += 1
                    streak += 1
                    self.bot.edge_streaks[username] = streak

                    stats.total_edges += 1
                    if streak > stats.current_streak:
                        stats.current_streak = streak
                    if streak > stats.highest_streak:
                        stats.highest_streak = streak
                    if streak > stats.longest_session:
                        stats.longest_session = streak

                    milestone_hit = None
                    if streak > old_pb and 'pb' not in self.bot.edge_milestones[username]:
                        milestone_hit = 'pb'
                        self.bot.edge_milestones[username].add('pb')
                        try:
                            sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'pb.mp3'), 0.5))
                            sound_thread.daemon = True
                            sound_thread.start()
                        except Exception as e:
                            logging.error(f"Error playing pb sound: {e}")
                        messages.append(f"🏆 {streak} That's a new PB {display_name}! 🏆")
                    elif streak == 69 and '69' not in self.bot.edge_milestones[username]:
                        milestone_hit = '69'
                        self.bot.edge_milestones[username].add('69')
                        try:
                            sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'nice.mp3'), 0.7))
                            sound_thread.daemon = True
                            sound_thread.start()
                        except Exception as e:
                            logging.error(f"Error playing nice sound: {e}")
                        messages.append(f"{streak}... Nice {display_name}")
                    elif streak == 100 and '100' not in self.bot.edge_milestones[username]:
                        milestone_hit = '100'
                        self.bot.edge_milestones[username].add('100')
                        try:
                            sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'choir.mp3'), 0.6))
                            sound_thread.daemon = True
                            sound_thread.start()
                        except Exception as e:
                            logging.error(f"Error playing choir sound: {e}")
                        messages.append(f"💯 {streak} TRIPLE DIGITS! {display_name} HAS ASCENDED!")
                    elif streak % 50 == 0:
                        messages.append(self._get_streak_message(streak, display_name))

                await asyncio.to_thread(session.commit)

                if num_attempts > 1 and not messages:
                    emote = random.choice(['🦴', '😏', '🔥', '💦', '👅', '🍆', '🍌', '🌭', '🌮', '👄'])
                    messages.append(f"Successfully edged {num_attempts} times! New streak: {streak} {emote}")
                elif not messages:
                    messages.append(self._get_streak_message(streak, display_name))

                if hasattr(self.bot, 'active_duels') and username in self.bot.active_duels:
                    duel = self.bot.active_duels[username]
                    challenger = list(self.bot.active_duels.keys())[0]
                    opponent = duel['opponent']
                    next_player = opponent if username == challenger else challenger
                    next_display = duel['opponent_display'] if username == challenger else duel['challenger_display']

                    duel['current_turn'] = next_player
                    messages.append(f"Your turn, {next_display}!")

                await ctx.send(" | ".join(messages))
                self.bot.user_last_edge_times[username] = current_time

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error in edge command: {e}")
            logging.error(f"Current edge_streaks state: {getattr(self.bot, 'edge_streaks', 'Not initialized')}")
            await ctx.send("Something went wrong with the edge!")

    def _calculate_recovery_time(self, streak: int, username: str) -> int:
        if hasattr(self.bot, 'active_blessings') and username in self.bot.active_blessings:
            if datetime.now() < self.bot.active_blessings[username]:
                return 0
            else:
                del self.bot.active_blessings[username]

        return int(streak * 1)

    async def _handle_bust(self, ctx, display_name, streak, stats, recovery_mins):
        from bot import play_sound
        try:
            try:
                if streak < 10:
                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'sadtrombone.mp3'), 0.4))
                elif streak >= 100:
                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'megabust.mp3'), 0.8))
                elif streak >= 50:
                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'bigbust.mp3'), 0.6))
                elif streak >= 10:
                    sound_thread = Thread(target=play_sound, args=(str(BASE_DIR / 'sounds' / 'bust.mp3'), 0.5))

                sound_thread.daemon = True
                sound_thread.start()
            except Exception as e:
                logging.error(f"Error playing bust sound: {e}")

            if streak >= 200:
                message = f"LEGENDARY FAILURE! {display_name}'s {streak} streak EXPLODED! That's one for the history books! ({recovery_mins}m recovery)"
            elif streak >= 100:
                message = f"CATASTROPHIC BUST! {display_name} lost control after {streak}! The cleanup crew has been notified! ({recovery_mins}m recovery)"
            elif streak >= 50:
                message = f"MASSIVE MESS! {display_name}'s {streak} streak ended with a bang! ({recovery_mins}m recovery)"
            else:
                bust_messages = [
                    f"{display_name} LOST CONTROL! {streak} streak OBLITERATED! ({recovery_mins}m recovery)",
                    f"CLEANUP ON AISLE {display_name}! {streak} streak GONE! ({recovery_mins}m recovery)",
                    f"OH NO NO NO! {display_name} COULDN'T HOLD BACK AFTER {streak}! ({recovery_mins}m recovery)",
                    f"RIP {display_name}'s {streak} streak... and their pants ({recovery_mins}m recovery)",
                    f"{display_name} just painted their ceiling after {streak}! ({recovery_mins}m recovery)",
                    f"Someone get {display_name} a towel! {streak} streak RUINED! ({recovery_mins}m recovery)",
                    f"{display_name}'s {streak} streak just went EVERYWHERE! ({recovery_mins}m recovery)",
                ]
                message = random.choice(bust_messages)

            if streak >= stats.highest_streak * 0.9:
                message += f" (Best: {stats.highest_streak})"

            await ctx.send(message)

        except Exception as e:
            logging.error(f"Error handling bust: {e}")
            await ctx.send(f"{display_name} busted after {streak}! ({recovery_mins}m recovery)")

    def _get_streak_message(self, streak: int, display_name: str) -> str:
        if streak > 100:
            messages = [
                f"{streak} {display_name} has become one with the edge!",
                f"{streak} Scientists cannot explain {display_name}!",
                f"{streak} {display_name} is writing the sacred texts!",
                f"{streak} The prophecy spoke of {display_name}'s coming!",
                f"{streak} {display_name} has mastered time and space!",
                f"{streak} The gods fear {display_name}'s control!",
                f"{streak} {display_name} exists in a state of pure edge!",
                f"{streak} Legends will tell of {display_name}'s restraint!",
                f"{streak} {display_name} has transcended human desire!",
                f"{streak} The ancient ones speak of {display_name}'s power",
                f"{streak} The universe trembles at {display_name}'s power"
            ]
        elif streak >= 50:
            messages = [
                f"{streak} {display_name} is reaching enlightenment!",
                f"{streak} {display_name}'s control is legendary!",
                f"{streak} The edge flows through {display_name}!",
                f"{streak} {display_name} has found inner peace!",
                f"{streak} {display_name} is approaching divinity!",
                f"{streak} {display_name} radiates pure energy!",
                f"{streak} {display_name} has mastered the ancient arts!",
                f"{streak} Time means nothing to {display_name} now"
            ]
        elif streak >= 25:
            messages = [
                f"{streak} {display_name} is showing impressive stamina!",
                f"{streak} {display_name} has iron will!",
                f"{streak} {display_name} is reaching new heights!",
                f"{streak} {display_name} knows the way!",
                f"{streak} {display_name} is in the zone!",
                f"{streak} {display_name} has found their rhythm!",
                f"{streak} {display_name} is becoming powerful!",
                f"{streak} The force is strong with {display_name}"
            ]
        else:
            messages = [
                f"{streak} {display_name} tests their limits!",
                f"{streak} {display_name} is learning control!",
                f"{streak} {display_name} takes another step!",
                f"{streak} {display_name} pushes forward!",
                f"{streak} {display_name} keeps it going!",
                f"{streak} {display_name} won't back down"
            ]

        emote = random.choice(['🦴', '😏', '🔥', '💦', '👅', '🍆', '🍌', '🌭', '🌮', '👄'])
        return f"{random.choice(messages)} {emote}"

    @commands.command(name='edgestats')
    async def edge_stats(self, ctx, username: str = None):
        try:
            target_user = (username or ctx.author.name).lower().lstrip('@')
            stats = await asyncio.to_thread(self.bot.db_manager.get_edge_stats, target_user)

            if not stats:
                await ctx.send(f"No edge stats found for {target_user}!")
                return

            user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
            display_name = user_context.get('nickname', target_user)

            if stats.total_busts > 0:
                ratio = stats.total_edges / stats.total_busts
                ratio_str = f"{ratio:.2f}"
            else:
                ratio_str = "∞"

            message = (
                f"{display_name}'s Edge Stats | "
                f"Best Streak: {stats.highest_streak} | "
                f"Total Edges: {stats.total_edges} | "
                f"Total Busts: {stats.total_busts} | "
                f"Edge/Bust Ratio: {ratio_str}% | "
                f"Last Streak: {stats.last_streak}"
            )

            await ctx.send(message)

        except Exception as e:
            logging.error(f"Error in edge_stats: {e}")
            await ctx.send("Couldn't get edge stats right now")

    @commands.command(name='edgetop', aliases=['topedge', 'topedges', 'edgelords'])
    async def edge_leaderboard(self, ctx):
        try:
            top_edgers = await asyncio.to_thread(self.bot.db_manager.get_edge_leaderboard)

            if not top_edgers:
                await ctx.send("No edge stats recorded yet!")
                return

            messages = ["Edge Leaderboard"]
            medals = ["1. ", "2. ", "3. "]

            for i, stat in enumerate(top_edgers, 1):
                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, stat.username)
                display_name = user_context.get('nickname', stat.username)

                if stat.total_busts > 0:
                    ratio = stat.total_edges / stat.total_busts
                    ratio_str = f"{ratio:.2f}"
                else:
                    ratio_str = "∞"

                if i <= 3:
                    medal = medals[i-1]
                    messages.append(f"{medal} {display_name}: {stat.highest_streak} (E/B: {ratio_str}%) ")
                else:
                    messages.append(f"{i}. {display_name}: {stat.highest_streak} (E/B: {ratio_str}%) ")

            await ctx.send(" | ".join(messages))

        except Exception as e:
            logging.error(f"Error in edge_leaderboard: {e}")
            await ctx.send("Couldn't get the edge leaderboard right now")

    @commands.command(name='duel')
    async def edge_duel(self, ctx, target: str = None):
        try:
            if not target:
                await ctx.send("You need to challenge someone! Usage: !duel @username")
                return

            challenger = ctx.author.name.lower()
            opponent = target.lower().lstrip('@')

            if challenger == opponent:
                await ctx.send("You can't duel yourself!")
                return

            if not hasattr(self.bot, 'active_duels'):
                self.bot.active_duels = {}
            if not hasattr(self.bot, 'pending_duels'):
                self.bot.pending_duels = {}

            if challenger in self.bot.active_duels or opponent in self.bot.active_duels:
                await ctx.send("One of you is already in a duel!")
                return

            if challenger in self.bot.pending_duels:
                await ctx.send(f"{challenger}, you already have a pending duel!")
                return

            challenger_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, challenger)
            opponent_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, opponent)
            challenger_display = challenger_context.get('nickname', challenger)
            opponent_display = opponent_context.get('nickname', opponent)

            self.bot.pending_duels[challenger] = {
                'opponent': opponent,
                'timestamp': datetime.now(),
                'challenger_display': challenger_display,
                'opponent_display': opponent_display
            }

            cooldown_note = ""
            if hasattr(self.bot, 'recovery_cooldowns') and opponent in self.bot.recovery_cooldowns:
                recovery_end = self.bot.recovery_cooldowns[opponent]
                current_time = datetime.now()
                if current_time < recovery_end:
                    remaining = (recovery_end - current_time).total_seconds()
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    cooldown_note = f" (Note: {opponent_display} is currently recovering for {minutes}m {seconds}s, but the cooldown will be suspended if they accept!)"

            await ctx.send(
                f"{challenger_display} has challenged {opponent_display} to an edge-off! "
                f"Both players' streaks will be reset to 0 for a fair duel. "
                f"{opponent_display}, type 'bring it on' to accept or 'no thanks' to decline.{cooldown_note}"
            )

        except Exception as e:
            self.bot.log_error(f"Error in edge_duel: {e}")
            await ctx.send("Sorry, something went wrong with the duel challenge!")


def prepare(bot):
    bot.add_cog(EdgeCog(bot))
