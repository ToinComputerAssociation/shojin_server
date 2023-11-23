import discord
from discord.ext import commands, tasks
import aiohttp
from typing import TypedDict, NotRequired

import json
from urllib import request
import requests
from bs4 import BeautifulSoup
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


class Shojin(commands.Cog):
    problems_json: dict[str, Problem]
    
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self):
        "コグのロード時の動作"
        await self.get_problems_json()
        await self.update_all_submissions()
        self.score_calc.start()

    async def cog_unload(self):
        "コグのアンロード時の動作"
        self.score_calc.cancel()

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

    async def update_all_submissions(self):
        "登録されたすべてのユーザーのデータをアップデートし、更新があれば通知する。"
        pass

    async def user_score_update(self, user, problem):
        "指定されたユーザーのスコアを加算し、通知する。"
        pass

    def get_score(self, user_rate, problem_diff):
        "ユーザーのレートと問題のdifficultyから獲得するポイントを計算する。"
        return 1000 * pow(2, (problem_diff - user_rate) / 400)

    @tasks.loop(seconds=600)
    async def score_calc():
        print("start update")
        await update_score()
        print("end update")


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
			
