import json
from urllib import request
import requests
from bs4 import BeautifulSoup
import os
import asyncio

class init:
    
    @classmethod    
    def all(cls):
        get.login_atcoder()
        
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


class get:
    
    session = requests.session()
    
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
        
    @classmethod
    def all_submissions_data(cls, user_id):
        unix_second = 1699206101
        api_url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unix_second}"
        response = requests.get(api_url)
        jsonData = response.json()
        return jsonData

    @classmethod
    def collectNewestAcceptedSubmissions(cls, submissions):
        submits = {}  # 各問題ごとに最新の提出に更新する
        for data in submissions:
            if data["result"] != "AC":  # ACだった提出だけ対象
                continue
            submits[data["problem_id"]] = submission(data["id"], data["problem_id"], data["contest_id"], data["user_id"])
        return submits

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
        json.dump(users, file, cls=user_encoder)
        
    @classmethod    
    def load_user_data(cls):
        file = open(cls.user_data_path , 'r')
        jsonData = json.load(file, cls=user_decoder)
        return jsonData


class user_encoder(json.JSONEncoder):
    
    def default(self, o):
        if isinstance(o, user):
            return {'_type': 'user', 'value': o.__dict__}
        return json.JSONEncoder.default(self, o)


class user_decoder(json.JSONDecoder):
    
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook,
                                  *args, **kwargs)

    def object_hook(self, o):
        if '_type' not in o:
            return o
        type = o['_type']
        if type == 'user':
            return user(**o['value'])