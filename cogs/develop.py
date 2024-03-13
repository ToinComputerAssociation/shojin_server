import discord
import json
from discord.ext import commands


class Develop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def fixpoint(self, ctx: commands.Context, user_id: str, before_diff: int, after_diff: int):
        "レートが変更された際にこのコマンドを使って再計算できます"
        cog = self.bot.cogs["Shojin"]
        user_rate = cog.users[user_id]["rating"]
        if before_diff < -10000:
            before_score = 0
        else:
            before_score = cog.get_score(user_rate, before_diff)
        before = cog.users[user_id]["score"]
        cog.users[user_id]["score"] -= before_score
        after_score = cog.get_score(user_rate, after_diff)
        cog.users[user_id]["score"] += after_score
        await ctx.send(f"{user_id}のスコアを更新しました。\n{before} -> {cog.users[user_id]['score']} (-{before_score:.3f} +{after_score:.3f})")

    @commands.command()
    async def diffdic(self, ctx: commands.Context, problem_id: str, diff: int):
        "特定の問題のdifficultyを登録します。"
        cog = self.bot.cogs["Shojin"]
        cog.diffdic[problem_id] = diff
        with open("data/difficulty_dictionary.json", mode="w") as f:
            json.dump(cog.diffdic, f)
        await ctx.send(f"問題 {problem_id} にdiff {diff} を設定しました。")


async def setup(bot):
    await bot.add_cog(Develop(bot))
