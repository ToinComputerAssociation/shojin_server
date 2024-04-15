import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="botのヘルプを表示します。")
    async def help(self, ctx):
        embed = discord.Embed(title="精進bot V2", description="prefixは`shojin.`と`/`の両方に対応しています。", color=discord.Color.blue())
        if ctx.interaction is not None:
            prefix = "/"
        else:
            prefix = "shojin."
        embed.add_field(name=f"{prefix}register", value="精進botに登録します。登録するとAC通知を受け取れるようになります。", inline=False)
        embed.add_field(name=f"{prefix}ranking", value="精進ポイントのランキングを表示します。", inline=False)
        embed.add_field(name=f"{prefix}status", value="自分のスコアやランキングでの順位などの情報を確認できます。", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
