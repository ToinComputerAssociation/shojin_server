import os
import time
import asyncio
import shoujin
import discord
from discord import app_commands
from discord.ext import tasks
from keep_alive import keep_alive

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)

CHANNEL_ID = 1173817847294734349

@client.event
async def on_ready():
    await tree.sync()
    loop.start()
    print('ログインしました')


users = shoujin.json_.load_user_data()
shoujin.main.init()
    
async def update_score():
    shoujin.main.update()
    unix_second = shoujin.time.load()
    submissions = await shoujin.get.submission_data(users, unix_second)    
    for submission in submissions:
        point = await shoujin.get.point(submission)
        users[submission.user_id].score += point
        if shoujin.time.load() < submission.epoch_second + 1:
            shoujin.time.save(submission.epoch_second + 1)
        print(f"{submission.user_id} get {point} point!")
        channel = client.get_channel(CHANNEL_ID)
        await channel.send(f"{submission.user_id}が{submission.problem_id}(diff:{submission.difficultiy})をACしました！\nscore:{round(users[submission.user_id].score - point, 3)} -> {round(users[submission.user_id].score, 3)}(+{round(point, 3)})")
    shoujin.json_.save_user_data(users)
    await asyncio.sleep(5)
    #pushGitHub()
    
#GitHubに保存
def pushGitHub():
    os.system('git add .')
    os.system(f'git config --global user.email "{os.environ["EMAIL"]}"')
    os.system('git config --global user.name "strawberry29"')
    os.system('git commit -m "update"')
    os.system('git push origin main')


@tasks.loop(seconds=600)
async def loop():
    print("start update")
    await update_score()
    print("end update")
    
    
keep_alive()
TOKEN = os.environ["DISCORD_TOKEN"]
client.run(TOKEN)


