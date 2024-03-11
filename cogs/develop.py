import discord
from discord.ext import commands


class Develop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def recalc(self, ctx: commands.Context, user_id: str, submit_id: int, before_rate: int):
        "レートが変更された際にこのコマンドを使って再計算できます"
        await ctx.send("開発中")


async def setup(bot):
    await bot.add_cog(Develop(bot))
