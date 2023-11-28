import discord
from discord.ext import commands, tasks
import aiohttp
from typing import TypedDict, NotRequired
import datetime
import time

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


class User(TypedDict):
    score: float
    rating: int
    discord_id: int


class Shojin(commands.Cog):
    problems_json: dict[str, Problem]
    users: dict[str, User]
    NOTICE_CHANNEL_ID = 1173817847294734349

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self):
        "コグのロード時の動作"
        with open("data/scores.json", mode="r") as f:
            self.users = json.load(f)
        with open("data/submissions.json", mode="r") as f:
            self.submissions = json.load(f)
        await self.get_problems_data()
        await self.update_all_submissions()
        await self.update_rating()
        self.score_calc.start()
        self.update_rating.start()

    async def cog_unload(self):
        "コグのアンロード時の動作"
        self.score_calc.cancel()
        self.update_rating.cancel()

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

    async def _get_20_minutes_submissions(self, user_id: str):
        "対象ユーザーの直近20分の提出の取得を行う。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            unixtime = int(time.time() - 1200)
            url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unixtime}"
            return await (await session.get(url)).json()

    async def update_all_submissions(self):
        "登録されたすべてのユーザーのデータをアップデートし、更新があれば通知する。"
        for user_id in self.users.keys():
            new_ac = await self.update_user_submissions(user_id)
            # 点数更新&通知
            if new_ac:
                await self.user_score_update(user_id, *new_ac)

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

    async def user_score_update(self, user_id, *problems):
        "指定されたユーザーのスコアを加算し、通知する。"
        channel = self.bot.get_channel(self.NOTICE_CHANNEL_ID)
        assert isinstance(channel, discord.TextChannel)

        if not problems:
            return False

        rate = self.users[user_id]["rating"]
        before = self.users[user_id]["score"]
        messages = []
        for problem_id in problems:
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

    async def get_rating(self, user_id, session):
        "ユーザーのレートを取得する。(AtCoderのサイトにアクセスする。)"
        response = await session.get(f"https://atcoder.jp/users/{user_id}/history/json")
        jsonData = await response.json()
        return jsonData[-1]["NewRating"]

    def get_score(self, user_rate, problem_diff):
        "ユーザーのレートと問題のdifficultyから獲得するポイントを計算する。"
        return 1000 * pow(2, (problem_diff - user_rate) / 400)

    @commands.command(aliases=["re"])
    async def register(self, ctx: commands.Context, user_id: str):
        if user_id in self.users:
            return await ctx.reply("このAtCoderユーザーは登録済みです。")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            rating = await self.get_rating(user_id, session)

        self.users[user_id] = {"score": 0, "discord_id": ctx.author.id, "rating": rating}
        await self.update_user_submissions(user_id)
        await ctx.reply("登録しました。")

    @tasks.loop(seconds=600)
    async def score_calc(self):
        # スコア更新の判定をする。
        for user_id in self.users.keys():
            submissions = await self._get_20_minutes_submissions(user_id)
            new_ac = []
            for sub in submissions:
                if sub["result"] == "AC":
                    if not self.submissions[user_id][sub["problem_id"]]:
                        # First AC
                        self.submissions[user_id][sub["problem_id"]] = True
                        new_ac.append(sub["problem_id"])
            await self.user_score_update(user_id, *new_ac)

    @tasks.loop(time=datetime.time(15, 0))
    async def update_rating(self):
        print("update users rating...")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            for user_id in self.users.keys():
                rating = await self.get_rating(user_id, session)
                self.users[user_id]["rating"] = rating
        print("Saving Data...")
        with open("data/submissions.json", mode="w") as f:
            json.dump(self.submissions, f)
        with open("data/scores.json", mode="w") as f:
            json.dump(self.users, f)


async def setup(bot):
    await bot.add_cog(Shojin(bot))
