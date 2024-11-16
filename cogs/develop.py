import discord
import json
from discord.ext import commands


class Develop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def fixpoint(self, ctx: commands.Context, user_id: str, before_diff: int, after_diff: int | None = None):
        "レートが変更された際にこのコマンドを使って再計算できます。"
        cog = self.bot.cogs["Shojin"]
        user_rate = cog.users[user_id]["rating"]
        before = cog.users[user_id]["score"]
        if after_diff is None:
            # この場合、before_diffがscoreの差分として繁栄される。
            cog.users[user_id]["score"] += before_diff
            async with self.bot.conn.cursor() as cursor:
                await cursor.execute("UPDATE Users SET score=? WHERE id=?;", (cog.users[user_id]["score"], user_id))
            await ctx.send(f"{user_id}のスコアを更新しました。\n{before} -> {cog.users[user_id]['score']} ({before_diff:+})")
            return
        if before_diff < -10000:
            before_score = 0
        else:
            before_score = cog.get_score(user_rate, before_diff)
        cog.users[user_id]["score"] -= before_score
        after_score = cog.get_score(user_rate, after_diff)
        cog.users[user_id]["score"] += after_score
        async with self.bot.conn.cursor() as cursor:
            await cursor.execute("UPDATE Users SET score=? WHERE id=?;", (cog.users[user_id]["score"], user_id))
        await ctx.send(f"{user_id}のスコアを更新しました。\n{before} -> {cog.users[user_id]['score']} (-{before_score:.3f} +{after_score:.3f})")

    @commands.command()
    async def diffdic(self, ctx: commands.Context, problem_id: str, diff: int):
        "特定の問題のdifficultyを登録します。"
        cog = self.bot.cogs["Shojin"]
        if problem_id in cog.diffdic:
            async with self.bot.conn.cursor() as cursor:
                await cursor.execute("UPDATE Diffdic SET difficulty=? WHERE problem_id=?;", (diff, problem_id))
        else:
            async with self.bot.conn.cursor() as cursor:
                await cursor.execute("INSERT INTO Diffdic VALUES (?, ?);", (problem_id, diff))
        cog.diffdic[problem_id] = diff
        await ctx.send(f"問題 {problem_id} にdiff {diff} を設定しました。")


async def setup(bot):
    await bot.add_cog(Develop(bot))
