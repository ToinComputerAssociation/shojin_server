from urllib import request
import requests
from bs4 import BeautifulSoup
import os

session = requests.session()
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
# 3. 認証完了後のページで他ページへ遷移を行う
url = "https://atcoder.jp/contests/cf17-final/submissions?f.Task=cf17_final_a&f.LanguageName=&f.Status=AC&f.User=strawberry0929"
req = session.get(url)
soup = BeautifulSoup(req.text, "html.parser")

first_ac_data_id = soup.find_all(attrs={"data-id": True})[-1]['data-id']
print(first_ac_data_id)
