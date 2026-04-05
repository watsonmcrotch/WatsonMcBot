import asyncio
import logging
from datetime import datetime
from twitchio.ext import commands
from models import TriviaStats, TriviaGame, TriviaRound


class TriviaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='triviastats')
    async def trivia_stats(self, ctx, username: str = None):
        try:
            target_user = (username or ctx.author.name).lower().lstrip('@')
            session = await asyncio.to_thread(self.bot.db_manager.get_session)

            try:
                stats = await asyncio.to_thread(
                    lambda: session.query(TriviaStats).filter_by(username=target_user).first()
                )
                if not stats:
                    await ctx.send(f"No trivia stats found for {target_user}!")
                    return

                user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, target_user)
                display_name = user_context.get('nickname', target_user)

                total_answers = stats.correct_answers + stats.wrong_answers
                accuracy = (stats.correct_answers / total_answers * 100) if total_answers > 0 else 0.0

                response = (
                    f"{display_name}'s Trivia Stats | "
                    f"Rounds: {stats.games_played} | "
                    f"Correct: {stats.correct_answers} | "
                    f"Wrong: {stats.wrong_answers} | "
                    f"Accuracy: {accuracy:.1f}% | "
                    f"Points: {stats.total_points}"
                )

                await ctx.send(response)

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error in trivia_stats: {e}")
            await ctx.send("Couldn't retrieve trivia stats right now!")

    @commands.command(name='lastgame')
    async def last_game_summary(self, ctx):
        try:
            session = await asyncio.to_thread(self.bot.db_manager.get_session)
            try:
                last_game = await asyncio.to_thread(
                    lambda: session.query(TriviaGame)
                    .order_by(TriviaGame.end_time.desc())
                    .first()
                )

                if not last_game:
                    await ctx.send("No previous games found!")
                    return

                initiator_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, last_game.initiator)
                initiator_display = initiator_context.get('nickname', last_game.initiator)

                winner_display = "No winner"
                if last_game.winner:
                    winner_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, last_game.winner)
                    winner_display = winner_context.get('nickname', last_game.winner)

                time_ago = datetime.now() - last_game.end_time
                minutes_ago = int(time_ago.total_seconds() / 60)

                response = (
                    f"Last Game Summary ({minutes_ago}m ago) | "
                    f"Host: {initiator_display} | "
                    f"Category: {last_game.category} | "
                    f"Players: {last_game.total_players} | "
                    f"Winner: {winner_display}"
                )

                await ctx.send(response)

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error in last_game_summary: {e}")
            await ctx.send("Couldn't retrieve the last game summary!")

    @commands.command(name='leaderboard', aliases=['triviatop', 'leaders', 'triviagame'])
    async def trivia_leaderboard(self, ctx):
        try:
            session = await asyncio.to_thread(self.bot.db_manager.get_session)
            try:
                top_players = await asyncio.to_thread(
                    lambda: session.query(TriviaStats)
                    .order_by(TriviaStats.total_points.desc())
                    .limit(5)
                    .all()
                )

                if not top_players:
                    await ctx.send("No trivia stats recorded yet!")
                    return

                messages = ["Trivia Leaderboard"]
                medals = ["1.", "2.", "3."]

                for i, stats in enumerate(top_players, 1):
                    user_context = await asyncio.to_thread(self.bot.db_manager.get_user_context, stats.username)
                    display_name = user_context.get('nickname', stats.username)

                    total_answers = float(stats.correct_answers or 0) + float(stats.wrong_answers or 0)
                    accuracy = (float(stats.correct_answers or 0) / total_answers * 100) if total_answers > 0 else 0.0

                    if i <= 3:
                        messages.append(
                            f"{medals[i-1]} {display_name}: {stats.total_points}pts "
                        )
                    else:
                        messages.append(
                            f"{i}. {display_name}: {stats.total_points}pts "
                        )

                await ctx.send(" | ".join(messages))

            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error in trivia_leaderboard: {e}", exc_info=True)
            await ctx.send("Couldn't retrieve the leaderboard right now!")


def prepare(bot):
    bot.add_cog(TriviaCog(bot))
