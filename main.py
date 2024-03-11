import traceback
import discord
from discord.ext import commands
import os
import dotenv

# cwdをこのファイルがある場所に移動
os.chdir(os.path.dirname(os.path.abspath(__file__)))


dotenv.load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    intents=intents, command_prefix="shojin.",
    allowed_mentions=discord.AllowedMentions.none()
)


bot.owner_ids = [
    866659388122202162,  # strawberry
    693025129806037003,  # yaakiyu
    850297484965576754,  # blueberry
]


@bot.event
async def on_ready():
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


bot.run(token=os.getenv("SHOJIN_BOT_TOKEN"))
