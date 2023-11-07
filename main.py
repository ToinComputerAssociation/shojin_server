import requests
import json
import time

lastgetSubmission = 1699206101
# APIを用いた提出データの取得
def getSubmissionData(user_id):
    unix_second = lastgetSubmission
    api_url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user_id}&from_second={unix_second}"
    response = requests.get(api_url)
    jsonData = response.json()
    return jsonData


submissions = getSubmissionData("strawberry0929")


# 各問題において最も新しいAC提出のみを取得する
def collectNewestAcceptedSubmissions(submissions):
    submits = {}  # 各問題ごとに最新の提出に更新する
    for data in submissions:
        if data["result"] != "AC":  # ACだった提出だけ対象
            continue
        submits[data["problem_id"]] = data
    return submits


newestSubmits = collectNewestAcceptedSubmissions(submissions)

for data in newestSubmits:
    print(data)
