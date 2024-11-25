import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
from typing import TypedDict, NotRequired
import datetime
import time
import utils


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


class ReNotifCache:
    "再AC通知用に、一時的に提出のデータを保管するためのクラス"

    def __init__(self, submit_ids: list[int]):
        self.submit_ids = {submit_id: time.time() for submit_id in submit_ids}

    @tasks.loop(seconds=1)
    async def garbage_collection(self):
        "再ACを確認してから12時間以上経ったものを削除する。"
        for k, v in self.submit_ids.items():
            if time.time() - v > 43200:
                del self.submit_ids[k]

    def append(self, item: int) -> None:
        self.submit_ids[item] = time.time()

    def __repr__(self) -> str:
        return f"<ReNotifCache submit_ids={self.submit_ids}>"

    def get(self, item):
        return self.submit_ids.get(item, False)


class Shojin(commands.Cog):
    problems_json: dict[str, Problem]
    users: dict[int, utils.User]
    diffdic: dict[str, int]
    NOTICE_CHANNEL_ID = 1173817847294734349
    SHOULD_REGISTER_MESSAGE = ("あなたはユーザー登録をしていません。\n"
    "`shojin.register <AtCoderユーザーID>`で登録してください。")

    def __init__(self, bot) -> None:
        self.bot = bot
        self.renotifcache = ReNotifCache([])

    async def cog_load(self):
        "コグのロード時の動作"
        async with self.bot.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM Users;")
            self.users = utils.make_users(await cursor.fetchall())
            await cursor.execute("SELECT * FROM Submissions;")
            self.submissions = utils.make_submissions(await cursor.fetchall())
            await cursor.execute("SELECT * FROM Diffdic;")
            self.diffdic = utils.make_diffdic(await cursor.fetchall())
        with open("data/last_allget_time.txt", mode="r") as f:
            self.last_allget_time = int(f.read())
        print("Getting all submissions and update...")
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

    async def _get_all_submissions(self, user_id: str, unixtime: int | None = None):
        "対象ユーザーの全提出データを取得する。"
        all_submissions = []
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            if unixtime is None:
                unixtime = self.last_allget_time
            while True:
                url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unixtime}"
                submissions = await (await session.get(url)).json()
                all_submissions.extend(submissions)
                if len(submissions) != 500:
                    break
                unixtime = submissions[-1]["epoch_second"]
                await asyncio.sleep(3)
        return all_submissions

    async def _get_30_minutes_submissions(self, user_id: str):
        "対象ユーザーの直近30分の提出の取得を行う。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            unixtime = int(time.time() - 1800)
            url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unixtime}"
            return await (await session.get(url)).json()

    async def update_all_submissions(self):
        "登録されたすべてのユーザーのデータをアップデートし、更新があれば通知する。"
        print("[log] fetching all submissions...")
        async with self.bot.conn.cursor() as cursor:
            for user_id in self.users.keys():
                new_ac = await self.update_user_submissions(user_id, cursor)
                # 点数更新&通知
                if new_ac:
                    await self.user_score_update(user_id, new_ac)
        self.last_allget_time = int(time.time()) - 86400
        with open("data/last_allget_time.txt", mode="w") as f:
            f.write(str(self.last_allget_time))

    async def update_user_submissions(self, discord_user_id: int, cursor, register=False) -> list[str]:
        "指定されたユーザーのデータを全取得して、新規ACの更新をする。"
        user_id = self.users[discord_user_id]["atcoder_id"]
        all_subs = await self._get_all_submissions(user_id, 0 if register else None)
        all_ac_subs = list(filter((lambda x: x["result"] == "AC"), all_subs))

        new_ac = []
        for sub in all_ac_subs:
            problem_id = sub["problem_id"]
            ac_time = sub["epoch_second"]

            if problem_id not in self.submissions[user_id]:
                self.submissions[user_id][problem_id] = ac_time
                new_ac.append(problem_id)
                await cursor.execute(
                    "INSERT INTO Submissions VALUES (?, ?, ?);",
                    (user_id, problem_id, ac_time)
                )
            elif ac_time > self.submissions[user_id][problem_id]:
                if self.submissions[user_id][problem_id] == 0:
                    new_ac.append(problem_id)
                self.submissions[user_id][problem_id] = ac_time
                await cursor.execute(
                    "UPDATE Submissions SET last_ac=? WHERE atcoder_id=? AND problem_id=?;",
                    (ac_time, user_id, problem_id)
                )

        self.users[discord_user_id]["solve_count"] += len(new_ac)
        # 新規ACを返す
        return new_ac

    async def user_score_update(self, user_id: int, problems: list):
        "指定されたユーザーのスコアを加算し、通知する。"
        channel = self.bot.get_channel(self.NOTICE_CHANNEL_ID)
        assert isinstance(channel, discord.TextChannel)

        rate = self.users[user_id]["rating"]
        if problems:
            before = self.users[user_id]["score"]
            messages = []
            for problem_id in problems:
                if "ahc" in problem_id:
                    continue
                diff = self.diffdic.get(problem_id, None)
                if diff is None:
                    diff = self.problems_json.get(problem_id, {}).get("difficulty", 400)
                contest_id = self.problems_json.get(problem_id, {}).get("contest_id", None)
                point = self.get_score(rate, diff)
                self.users[user_id]["score"] += point
                messages.append(f"[{problem_id}](<https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}>)(diff:{diff})")
            
            if not self.users[user_id]["notif_setting"]:
                return
            # メッセージの用意
            after = self.users[user_id]["score"]
            user_name = self.users[user_id]["atcoder_id"]
            content = f"{user_name}(rate:{rate})が{', '.join(messages)}をACしました！\nscore:{before:.3f} -> {after:.3f}(+{after - before:.3f})"
            if len(messages) != 0:
                if len(content) > 2000:
                    await channel.send(f"{user_name}(rate:{rate})が{len(messages)}問の問題をACしました！\n{content.splitlines()[-1]}")
                else:
                    await channel.send(content)
            # データ保存
            async with self.bot.conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE Users SET score=?, solve_count=? WHERE id=?;",
                    (after, self.users[user_id]["solve_count"], user_id)
                )

    async def get_rating(self, user_id: str, session):
        "ユーザーのレートを取得する。(AtCoderのサイトにアクセスする。)"
        response = await session.get(f"https://atcoder.jp/users/{user_id}/history/json")
        jsonData = await response.json()
        return jsonData[-1]["NewRating"]

    def get_score(self, user_rate, problem_diff):
        "ユーザーのレートと問題のdifficultyから獲得するポイントを計算する。"
        return pow(2, (problem_diff - user_rate) / 400) * (1000 + max(0, problem_diff))

    def get_user_from_discord(self, discord_id: int):
        if discord_id in self.users:
            return self.users[discord_id]["atcoder_id"]
        return False

    @commands.hybrid_command(aliases=["re"], description="精進通知をオンにします。")
    @app_commands.describe(user_id="AtCoderのユーザーID")
    async def register(self, ctx: commands.Context, user_id: str):
        if ctx.author.id in self.users:
            return await ctx.reply("あなたは登録済みです。")
        if user_id in [x["atcoder_id"] for x in self.users.values()]:
            return await ctx.reply("このAtCoderユーザーは登録済みです。")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            rating = await self.get_rating(user_id, session)

        msg = await ctx.reply("登録しています...(この操作は数分かかる場合があります)")
        self.users[ctx.author.id] = {
            "score": 0, "atcoder_id": user_id, "rating": rating, "solve_count": 0,
            "notif_setting": True
        }
        self.submissions[user_id] = {}
        async with self.bot.conn.cursor() as cursor:
            await self.update_user_submissions(ctx.author.id, cursor, register=True)
            await cursor.execute(
                "INSERT INTO Users VALUES (?, ?, ?, ?, ?, ?)",
                (ctx.author.id, 0, user_id, 0, rating, True)
            )
        await msg.edit(content="登録しました。")

    @commands.hybrid_command(description="現在のスコアを確認します。")
    async def status(self, ctx: commands.Context, user: discord.User = commands.Author):
        if user.id not in self.users:
            if user != ctx.author:
                return await ctx.send("この人はユーザー登録をしていません。")
            return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
        await ctx.send(
            f"{user.mention}のデータ\nAtCoder ID：{user.id}\nbot内で保存されている"
            f"レーティング：{self.users[user.id]['rating']}\n(今シーズン)スコア：{self.users[user.id]['score']}"
            f"\n(今シーズン)解いた問題数: {self.users[user.id]['solve_count']}",
            allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.hybrid_command(description="精進ポイントのランキングを表示します。")
    async def ranking(self, ctx: commands.Context, rank: str = "1"):
        points = [
            (self.users[user_id]["atcoder_id"], self.users[user_id]["score"],
             self.users[user_id]["solve_count"])
            for user_id in self.users.keys()
        ]
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
            rank = max(0, min(int(rank), len(points)-4) - 1)
        messages = []
        for i in range(5):
            now = rank + i
            if now >= len(points):
                break
            messages.append(
                f"{now+1}位：**`{points[now][0]}`** (score: `{points[now][1]:.3f}` 解いた問題数: {points[now][2]})"
            )
        await ctx.send("\n".join(messages))

    @commands.hybrid_group(description="設定の変更をします。")
    async def settings(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            if ctx.author.id not in self.users:
                return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
            t = ["オフ", "オン"][int(self.users[ctx.author.id]["notif_setting"])]
            await ctx.send("あなたの設定状況\n- AC通知(`shojin.settings notif`)：" + t)

    @settings.command(description="AC通知のオンオフを切り替えます")
    async def notif(self, ctx: commands.Context, onoff: bool | None = None):
        if ctx.author.id not in self.users:
            return await ctx.send(self.SHOULD_REGISTER_MESSAGE)
        if onoff is None:  # オンオフが指定されてなければ今の設定の反対にする
            onoff = not self.users[ctx.author.id]["notif_setting"]
        self.users[ctx.author.id]["notif_setting"] = onoff
        async with self.bot.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE Users SET notif_setting=? WHERE id=?",
                (onoff, ctx.author.id)
            )
        t = ["オフ", "オン"][int(onoff)]
        await ctx.send(f"`{t}`に設定しました。")

    @tasks.loop(seconds=600)
    async def score_calc(self):
        # スコア更新の判定をする。
        for user_id in self.users.keys():
            submissions = await self._get_30_minutes_submissions(user_id)
            new_ac = []
            re_ac = set()
            for sub in submissions:
                if isinstance(sub, str):
                    print(sub)
                    continue
                if sub["result"] == "AC":
                    if sub["problem_id"] not in self.problems_json:
                        await self.get_problems_data()
                    if not self.submissions[user_id].get(sub["problem_id"], False):
                        # First AC
                        self.submissions[user_id][sub["problem_id"]] = True
                        self.users[user_id]["solve_count"] += 1
                        new_ac.append(sub["problem_id"])
            await self.user_score_update(user_id, new_ac)

    @tasks.loop(time=datetime.time(15, 0))
    async def update_rating(self):
        print("[log] Update users rating...")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            for user_id in self.users.keys():
                rating = await self.get_rating(self.users[user_id]["atcoder_id"], session)
                if self.users[user_id]["rating"] != rating:
                    self.users[user_id]["rating"] = rating
                    # データ保存
                    async with self.bot.conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE Users SET rating = ? WHERE id = ?",
                            (rating, user_id)
                        )
                await asyncio.sleep(5)
        await self.get_problems_data()
        await self.update_all_submissions()
        await self.bot.conn.commit()


async def setup(bot):
    await bot.add_cog(Shojin(bot))
