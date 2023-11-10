import json
from urllib import request
import requests
from bs4 import BeautifulSoup
import os
import asyncio

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
    
    def __init__(self, id, problem_id, contest_id, user_id):
        self.id = id
        self.problem_id = problem_id
        self.contest_id = contest_id
        self.user_id = user_id

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
        return jsonData["time"]
        

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

    #submissionで得られる得点を計算
    @classmethod
    async def point(cls, submission):
        difficultiy = cls.difficulties.get(submission.problem_id, {}).get('difficulty', 400)
        rate = get.rating(submission.user_id)
        basic_point = 1000
        return basic_point * pow(2, (difficultiy - rate) / 400)

    @classmethod
    async def submission_data(cls, users):
        submissions = []
        for user in users.values():
            await asyncio.sleep(1)
            all_submissions = get.all_submissions_data(user.id)
            newest_submissions = get.collectNewestAcceptedSubmissions(all_submissions)
            for submission in newest_submissions.values():
                await asyncio.sleep(1)
                if get.isFirstAC(submission):
                    submissions.append(submission)
        return submissions

    # APIを用いた提出データの取得
    @classmethod
    def all_submissions_data(cls, user_id):
        unix_second = 1699206101
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
            submits[data["problem_id"]] = submission(data["id"], data["problem_id"], data["contest_id"], data["user_id"])
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
			