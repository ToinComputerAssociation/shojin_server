import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from typing import TypedDict, NotRequired
import datetime
import time
import os
import json


class Problem(TypedDict):
    id: str
    contest_id: str
    problem_index: str
    name: str
    title: str
    slope: NotRequired[float]
    intercept: NotRequired[float]
    variance: NotRequired[float]
    difficulty: NotRequired[int]
    discrimination: NotRequired[float]
    irt_loglikelihood: NotRequired[float]
    irt_users: NotRequired[int]
    is_experimental: bool


class Settings(TypedDict):
    renotif: bool


class User(TypedDict):
    score: float
    rating: int
    discord_id: int
    settings: Settings


class Shojin(commands.Cog):
    problems_json: dict[str, Problem]
    users: dict[str, User]
    NOTICE_CHANNEL_ID = 1173817847294734349
    SHOULD_REGISTER_MESSAGE = ("あなたはユーザー登録をしていません。\n"
    "`shojin.register <AtCoderユーザーID>`で登録してください。")

    def __init__(self, bot) -> None:
        self.bot = bot
        self.ten_minute_count = 0

    async def cog_load(self):
        "コグのロード時の動作"
        with open("data/scores.json", mode="r") as f:
            self.users = json.load(f)
        with open("data/submissions.json", mode="r") as f:
            self.submissions = json.load(f)
        print("Getting all submissions and update...")
        await self.get_problems_data()
        await self.update_all_submissions()
        await self.update_rating()
        self.score_calc.start()
        self.update_rating.start()

    async def cog_unload(self):
        "コグのアンロード時の動作"
        self.score_calc.cancel()
        self.update_rating.cancel()
        self.save_data()

    async def get_problems_data(self):
        "Atcoder Problems APIから全問題のdifficultyなどのデータを取得する。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            url = "https://kenkoooo.com/atcoder/resources/problems.json"
            self.problems_json = {i["id"]: i for i in (await (await session.get(url)).json())}
            url = "https://kenkoooo.com/atcoder/resources/problem-models.json"
            difficulties = await (await session.get(url)).json()
            for k, v in difficulties.items():
                if self.problems_json.get(k):
                    self.problems_json[k].update(v)
                else:
                    self.problems_json[k] = v

    async def _get_all_submissions(self, user_id: str):
        "対象ユーザーの全提出データを取得する。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            url = f"https://kenkoooo.com/atcoder/atcoder-api/results?user={user_id}"
            return await (await session.get(url)).json()

    async def _get_30_minutes_submissions(self, user_id: str):
        "対象ユーザーの直近30分の提出の取得を行う。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            unixtime = int(time.time() - 1800)
            url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unixtime}"
            return await (await session.get(url)).json()

    async def update_all_submissions(self):
        "登録されたすべてのユーザーのデータをアップデートし、更新があれば通知する。"
        for user_id in self.users.keys():
            new_ac = await self.update_user_submissions(user_id)
            # 点数更新&通知
            if new_ac:
                await self.user_score_update(user_id, new_ac)

    async def update_user_submissions(self, user_id: str) -> list[str]:
        "指定されたユーザーのデータを全取得して、新規ACの更新をする。"
        all_subs = await self._get_all_submissions(user_id)
        all_ac_subs = list(filter((lambda x: x["result"] == "AC"), all_subs))
        all_ac_problems = set([i["problem_id"] for i in all_ac_subs])
        if user_id not in self.submissions:
            self.submissions[user_id] = {k: k in all_ac_problems for k in self.problems_json.keys()}
            return False

        new_ac = []
        for problem_id in all_ac_problems:
            if not self.submissions[user_id].get(problem_id, False):
                new_ac.append(problem_id)
                self.submissions[user_id][problem_id] = True
        # 新規ACを返す
        return new_ac

    async def user_score_update(self, user_id, problems, re_ac_problems=[]):
        "指定されたユーザーのスコアを加算し、通知する。"
        channel = self.bot.get_channel(self.NOTICE_CHANNEL_ID)
        assert isinstance(channel, discord.TextChannel)

        if not problems:
            return

        rate = self.users[user_id]["rating"]
        before = self.users[user_id]["score"]
        messages = []
        for problem_id in problems:
            if "ahc" in problem_id:
                continue
            diff = self.problems_json.get(problem_id, {}).get("difficulty", 400)
            contest_id = self.problems_json.get(problem_id, {}).get("contest_id", None)
            point = self.get_score(rate, diff)
            self.users[user_id]["score"] += point
            messages.append(f"[{problem_id}](<https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}>)(diff:{diff})")
        after = self.users[user_id]["score"]
        await channel.send(
            f"{user_id}(rate:{rate})が{', '.join(messages)}をACしました！\n"
            f"score:{before:.3f} -> {after:.3f}(+{after - before:.3f})"
        )
        if not re_ac_problems:
            return
        points = 0
        for problem_id in re_ac_problems:
            diff = self.problems_json.get(problem_id, {}).get("difficulty", 400)
            contest_id = self.problems_json.get(problem_id, {}).get("contest_id", None)
            points += self.get_score(rate, diff)
            messages.append(f"[{problem_id}](<https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}>)(diff:{diff})")
        await channel.send(
            f"{user_id}(rate:{rate})が{', '.join(messages)}を再ACしました！\n"
            f"(想定獲得スコア：{points})"
        )

    async def get_rating(self, user_id, session):
        "ユーザーのレートを取得する。(AtCoderのサイトにアクセスする。)"
        response = await session.get(f"https://atcoder.jp/users/{user_id}/history/json")
        jsonData = await response.json()
        return jsonData[-1]["NewRating"]

    def get_score(self, user_rate, problem_diff):
        "ユーザーのレートと問題のdifficultyから獲得するポイントを計算する。"
        return 1000 * pow(2, (problem_diff - user_rate) / 400)

    def get_user_from_discord(self, discord_id: int):
        for user_id in self.users.keys():
            if self.users[user_id]["discord_id"] == discord_id:
                return user_id
        return False

    @commands.hybrid_command(aliases=["re"], description="精進通知をオンにします。")
    @app_commands.describe(user_id="AtCoderのユーザーID")
    async def register(self, ctx: commands.Context, user_id: str):
        if user_id in self.users:
            return await ctx.reply("このAtCoderユーザーは登録済みです。")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            rating = await self.get_rating(user_id, session)

        self.users[user_id] = {"score": 0, "discord_id": ctx.author.id, "rating": rating}
        self.users[user_id]["settings"] = Settings({"renotif": False})
        await self.update_user_submissions(user_id)
        await ctx.reply("登録しました。")

    @commands.hybrid_command(description="現在のスコアを確認します。")
    async def status(self, ctx: commands.Context, user: discord.User = commands.Author):
        user_id = self.get_user_from_discord(user.id)
        if not user_id:
            if user != ctx.author:
                return await ctx.send("この人はユーザー登録をしていません。")
            return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
        await ctx.send(
            f"{user.mention}のデータ\nAtCoder ID：{user_id}\nbot内で保存されている"
            f"レーティング：{self.users[user_id]['rating']}\nスコア：{self.users[user_id]['score']}",
            allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.hybrid_command(description="精進ポイントのランキングを表示します。")
    async def ranking(self, ctx: commands.Context, rank: str = "1"):
        points = [(user_id, self.users[user_id]["score"]) for user_id in self.users.keys()]
        points.sort(key=lambda i: i[1], reverse=True)
        if not rank.isdigit():
            if not self.users.get(rank, False):
                return await ctx.send("このユーザーは登録されていません。")
            for i in range(len(points)):
                if points[i][0] == rank:
                    rank = i
        elif int(rank) < 1:
            user_id = self.get_user_from_discord(ctx.author.id)
            if not user_id:
                return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
            for i in range(len(points)):
                if points[i][0] == user_id:
                    rank = i
        else:
            rank = min(int(rank), len(points)-4) - 1
        messages = []
        for i in range(min(5, len(self.users)-rank)):
            now = rank + i
            messages.append(
                f"{now+1}位：**`{points[now][0]}`** (score: `{points[now][1]:.3f}`)"
            )
        await ctx.send("\n".join(messages))

    @commands.hybrid_group(description="設定の変更をします。")
    async def settings(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            user_id = self.get_user_from_discord(ctx.author.id)
            if not user_id:
                return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
            t = ["オフ", "オン"][int(self.users[user_id]["settings"]["renotif"])]
            await ctx.send("あなたの設定状況\n- 再ACの通知(`shojin.settings renotif`)：" + t)

    @settings.command(description="再ACの通知のオンオフを切り替えます")
    async def renotif(self, ctx: commands.Context, onoff: bool | None = None):
        user_id = self.get_user_from_discord(ctx.author.id)
        if not user_id:
            return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
        if onoff is None:
            self.users[user_id]["settings"]["renotif"] = not self.users[user_id]["settings"]["renotif"]
        else:
            self.users[user_id]["settings"]["renotif"] = onoff
        t = ["オフ", "オン"][int(self.users[user_id]["settings"]["renotif"])]
        await ctx.send(f"`{t}`に設定しました。")

    @tasks.loop(seconds=600)
    async def score_calc(self):
        # スコア更新の判定をする。
        for user_id in self.users.keys():
            submissions = await self._get_30_minutes_submissions(user_id)
            new_ac = []
            for sub in submissions:
                if sub["result"] == "AC":
                    if not self.submissions[user_id].get(sub["problem_id"], False):
                        # First AC
                        self.submissions[user_id][sub["problem_id"]] = True
                        new_ac.append(sub["problem_id"])
            await self.user_score_update(user_id, new_ac)

    @tasks.loop(time=datetime.time(15, 0))
    async def update_rating(self):
        print("update users rating...")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            for user_id in self.users.keys():
                rating = await self.get_rating(user_id, session)
                self.users[user_id]["rating"] = rating
        self.save_data()

    def save_data(self):
        print("Saving Data...")
        with open("data/submissions.json", mode="w") as f:
            json.dump(self.submissions, f)
        with open("data/scores.json", mode="w") as f:
            json.dump(self.users, f)
        # バックアップをとる。
        today = datetime.date.today()
        with open(f"data/backup/{today.strftime(r'%Y%m%d')}.json", mode="w") as f:
            json.dump(self.submissions, f)
        with open(f"data/backup/{today.strftime(r'%Y%m%d')}_users.json", mode="w") as f:
            json.dump(self.users, f)
        weekago = today - datetime.timedelta(days=7)
        # 7日で自動削除
        if os.path.isfile(f"data/backup/{weekago.strftime(r'%Y%m%d')}.json"):
            os.remove(f"data/backup/{weekago.strftime(r'%Y%m%d')}.json")
        if os.path.isfile(f"data/backup/{weekago.strftime(r'%Y%m%d')}_users.json"):
            os.remove(f"data/backup/{weekago.strftime(r'%Y%m%d')}_users.json")


async def setup(bot):
    await bot.add_cog(Shojin(bot))
