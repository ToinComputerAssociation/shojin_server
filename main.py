import traceback
import discord
from discord.ext import commands
import os
import dotenv
import asqlite

# cwdをこのファイルがある場所に移動
os.chdir(os.path.dirname(os.path.abspath(__file__)))


dotenv.load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    intents=intents, command_prefix="shojin.",
    allowed_mentions=discord.AllowedMentions.none(),
    help_command=None
)


bot.owner_ids = [
    693025129806037003,  # yaakiyu
    850297484965576754,  # blueberry
]


@bot.check
async def is_command_available(ctx):
    return ctx.author.id in bot.owner_ids or ctx.guild.id == 1173817847294734346


@bot.event
async def on_ready():
    bot.conn = await asqlite.connect("data.db", isolation_level=None)  # autocommit
    async with bot.conn.cursor() as cursor:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Users(
                id BIGINT PRIMARY KEY NOT NULL, score REAL, atcoder_id TEXT UNIQUE,
                solve_count BIGINT, rating INTEGER, notif_setting BOOLEAN Default 1
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Submissions(
                atcoder_id TEXT, problem_id TEXT, last_ac BIGINT,
                PRIMARY KEY (atcoder_id, problem_id)
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Diffdic(
                problem_id TEXT PRIMARY KEY NOT NULL, difficulty INTEGER
            );"""
        )
    await bot.load_extension("jishaku")
    for name in os.listdir("./cogs"):
        if not name.startswith((".", "_")):
            try:
                await bot.load_extension("cogs."+name.replace(".py", ""))
            except Exception as e:
                print("".join(traceback.format_exception(e)))
    await bot.tree.sync()
    print("[log] Just ready for ShojinBot")


@bot.tree.error
async def on_error(interaction, error):
    await discord.app_commands.CommandTree.on_error(bot.tree, interaction, error)
    err = "".join(traceback.format_exception(error))
    embed = discord.Embed(description=f"```py\n{err}\n```"[:4095])
    if interaction.response.is_done():
        await interaction.channel.send("An error has occurred.", embed=embed)
    else:
        await interaction.response.send_message("An error has occurred.", embed=embed)


bot.run(token=os.getenv("TOKEN"))
