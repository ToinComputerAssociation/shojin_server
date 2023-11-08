import json
import os
import time
from urllib import request
import requests
from bs4 import BeautifulSoup
import asyncio
from collections import deque

session = requests.session()


# atcoderにログイン
def login_atcoder():
    url_login = "https://atcoder.jp/login?lang=ja"
    # ログインページへのアクセス完了
    req_before_login = session.get(url_login)

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
    req_after_login = session.post(url_login, data=login_data)


lastgetSubmission = 1699296101


# APIを用いた提出データの取得
def getSubmissionData(user_id):
    unix_second = lastgetSubmission
    api_url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unix_second}"
    response = requests.get(api_url)
    jsonData = response.json()
    return jsonData


# 各問題において最も新しいAC提出のみを取得する
def collectNewestAcceptedSubmissions(submissions):
    submits = {}  # 各問題ごとに最新の提出に更新する
    for data in submissions:
        if data["result"] != "AC":  # ACだった提出だけ対象
            continue
        submits[data["problem_id"]] = data
    return submits


#初めてのACか判定
async def isFirstAC(submission):
    await asyncio.sleep(1)
    url = f"https://atcoder.jp/contests/{submission['contest_id']}/submissions?f.Task={submission['problem_id']}&f.LanguageName=&f.Status=AC&f.User={submission['user_id']}"
    req = session.get(url)
    soup = BeautifulSoup(req.text, "html.parser")
    first_ac_data_id = soup.find_all(attrs={"data-id": True})[-1]['data-id']#一番最初にACした提出のidを取得
    return int(first_ac_data_id) == submission['id']


def getDifficulties():
    api_url = "https://kenkoooo.com/atcoder/resources/problem-models.json"
    response = requests.get(api_url)
    jsonData = response.json()
    return jsonData


def getRating(username):
    response = requests.get(f"https://atcoder.jp/users/{username}/history/json")
    jsonData = response.json()
    return jsonData[-1]["NewRating"]

def point_calculation(submission, difficultiy):
    rate = getRating(submission['user_id'])
    rate = 0
    basic_point = 1000
    return basic_point * pow(2, (difficultiy - rate) / 400)
	
submissions = getSubmissionData("strawberry0929")
newestSubmits = collectNewestAcceptedSubmissions(submissions)
login_atcoder()
difficulties = getDifficulties()
firstAC_submissions = deque()
for submission in newestSubmits.values():
    isFirst = asyncio.run(isFirstAC(submission))
    if isFirst:
        firstAC_submissions.append(submission)
while len(firstAC_submissions) != 0:
    submission = firstAC_submissions.popleft()
    difficultiy = difficulties[submission['problem_id']]['difficulty']
    print(difficultiy, point_calculation(submission, difficultiy))
os.system('git add .')
os.system(f'git config --global user.email "{os.environ["EMAIL"]}"')
os.system('git config --global user.name "strawberry29"')
os.system('git commit -m "update"')
os.system('git push origin main')

