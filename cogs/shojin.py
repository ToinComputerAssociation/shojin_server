import discord
from discord.ext import commands, tasks
import aiohttp
from typing import TypedDict, NotRequired
import datetime
import time

import orjson
from urllib import request
import requests
#from bs4 import BeautifulSoup
import os
import asyncio


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
            self.users = orjson.load(f)
        with open("data/submissions.json", mode="r") as f:
            self.submissions = orjson.load(f)
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
                self.problems_json[k].update(v)

    async def _get_all_submissions(self, user_id: str):
        "対象ユーザーの全提出データを取得する。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            url = f"https://kenkoooo.com/atcoder/atcoder-api/results?user={user_id}"
            return await (await session.get(url)).json()

    async def _get_20_minutes_submissions(self, user_id: str):
        "対象ユーザーの直近20分の提出の取得を行う。"
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            unixtime = time.time() - 1200
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
            if not self.submissions[user_id][problem_id]:
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
            messages.append(f"[{problem_id}](https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}) (diff:{diff})")
        after = self.users[user_id]["score"]
        await channel.send(
            f"{user_id}(rate:{rate})が{', '.join(messages)}をACしました！\n"
            f"score:{before:.3f} -> {after:.3f}(+{after - before:.3f})"
        )

    def get_score(self, user_rate, problem_diff):
        "ユーザーのレートと問題のdifficultyから獲得するポイントを計算する。"
        return 1000 * pow(2, (problem_diff - user_rate) / 400)

    @commands.command(aliases=["re"])
    async def register(self, ctx: commands.Context, user_id: str):
        if user_id in self.users:
            return await ctx.reply("このAtCoderユーザーは登録済みです。")
        async with aiohttp.ClientSession(loop=self.bot.loop) as session:
            url = f"https://us-central1-atcoderusersapi.cloudfunctions.net/api/info/username/{user_id}"

        self.users[user_id] = {"score": 0, "discord_id": ctx.author.id, "rating": 0}
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
            url = "https://us-central1-atcoderusersapi.cloudfunctions.net/api/info/username/"
            for user_id in self.users.keys():
                data = await (await session.get(url + user_id)).json()
                self.users[user_id]["rating"] = data["data"]["rating"]


async def setup(bot):
    await bot.add_cog(Shojin(bot))


class main:
    
    @classmethod    
    def init(cls):
        get.login_atcoder()
        main.update()

    @classmethod    
    def update(cls):
        get.all_difficulties()
        
class user:
    
    def __init__(self, id, discord_id, score = 0):
        self.id = id
        self.discord_id = discord_id
        self.score = score


class submission:
    
    def __init__(self, submission):
        self.id = submission["id"]
        self.epoch_second = submission["epoch_second"]
        self.problem_id = submission["problem_id"]
        self.contest_id = submission["contest_id"]
        self.user_id = submission["user_id"]

    @property
    def difficultiy(self):
        return get.difficultiy(self)

class time:

    time_path = "time.json"
    
    @classmethod
    def save(cls, time):
        file = open(cls.time_path, 'w')
        json.dump({"time" : time}, file)
        
    @classmethod    
    def load(cls):
        file = open(cls.time_path , 'r')
        jsonData = json.load(file)
        return int(jsonData["time"])
        

class get:
    
    session = requests.session()
    difficulties = {}
    
    @classmethod
    def login_atcoder(cls):#atcoderにログイン
        url_login = "https://atcoder.jp/login?lang=ja"
        # ログインページへのアクセス完了
        req_before_login = cls.session.get(url_login)
    
        # ログインするための情報を準備する
        login_data = {
            "username": os.environ["USERNAME"],
            "password": os.environ["PASWORD"]
        }
    
        # ログインするためにcsrfトークンが必要となるため情報を取得
        bs = BeautifulSoup(req_before_login.text, "html.parser")
        csrf_token = bs.find(attrs={"name": "csrf_token"}).get("value")
        login_data["csrf_token"] = csrf_token
    
        # 2. ログインページで認証を行い、管理者ページへ遷移する
        req_after_login = cls.session.post(url_login, data=login_data)

    #Atcoder Problemsからdifficultiyを取得
    @classmethod
    def all_difficulties(cls):
        api_url = "https://kenkoooo.com/atcoder/resources/problem-models.json"
        response = requests.get(api_url)
        jsonData = response.json()
        cls.difficulties = jsonData

    #user_idの現在のレートを取得
    @classmethod
    def rating(cls, user_id):
        response = requests.get(f"https://atcoder.jp/users/{user_id}/history/json")
        jsonData = response.json()
        return jsonData[-1]["NewRating"]
        
    #submissionのdifficultyを取得
    @classmethod
    def difficultiy(cls, submission):
        difficultiy = cls.difficulties.get(submission.problem_id, {}).get('difficulty', 400)
        return difficultiy
        
    #submissionで得られる得点を計算
    @classmethod
    async def point(cls, submission):
        difficultiy = cls.difficulties.get(submission.problem_id, {}).get('difficulty', 400)
        rate = get.rating(submission.user_id)
        basic_point = 1000
        return basic_point * pow(2, (difficultiy - rate) / 400)

    #有効な提出を取得
    @classmethod
    async def submission_data(cls, users, unix_second):
        submissions = []
        for user in users.values():
            await asyncio.sleep(1)
            all_submissions = get.all_submissions_data(user.id, unix_second)
            newest_submissions = get.collectNewestAcceptedSubmissions(all_submissions)
            for submission in newest_submissions.values():
                await asyncio.sleep(1)
                if get.isFirstAC(submission):
                    submissions.append(submission)
        return submissions

    # APIを用いた提出データの取得
    @classmethod
    def all_submissions_data(cls, user_id, unix_second):
        api_url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unix_second}"
        response = requests.get(api_url)
        jsonData = response.json()
        return jsonData

    # 各問題において最も新しいAC提出のみを取得する
    @classmethod
    def collectNewestAcceptedSubmissions(cls, submissions):
        submits = {}  # 各問題ごとに最新の提出に更新する
        for data in submissions:
            if data["result"] != "AC":  # ACだった提出だけ対象
                continue
            submits[data["problem_id"]] = submission(data)
        return submits

    #初めてのACか判定
    @classmethod
    def isFirstAC(cls, submission):
        url = f"https://atcoder.jp/contests/{submission.contest_id}/submissions?f.Task={submission.problem_id}&f.LanguageName=&f.Status=AC&f.User={submission.user_id}"
        req = cls.session.get(url)
        soup = BeautifulSoup(req.text, "html.parser")
        first_ac_data_id = soup.find_all(attrs={"data-id": True})[-1]['data-id']#一番最初にACした提出のidを取得
        return int(first_ac_data_id) == submission.id


class json_:
    
    user_data_path = "user.json"
    
    @classmethod
    def save_user_data(cls, users):
        file = open(cls.user_data_path, 'w')
        json.dump(users, file, cls=encoder)
        
    @classmethod    
    def load_user_data(cls):
        file = open(cls.user_data_path , 'r')
        jsonData = json.load(file, cls=decoder)
        return jsonData


class encoder(json.JSONEncoder):
    
    def default(self, o):
        if isinstance(o, user):
            return {'_type': 'user', 'value': o.__dict__}
        return json.JSONEncoder.default(self, o)


class decoder(json.JSONDecoder):
    
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook,
                                  *args, **kwargs)

    def object_hook(self, o):
        if '_type' not in o:
            return o
        type = o['_type']
        if type == 'user':
            return user(**o['value'])
        if type == 'submission':
            return user(**o['value'])
			
