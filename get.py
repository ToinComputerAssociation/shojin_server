from urllib import request
import requests
from bs4 import BeautifulSoup
import os
url_login = "https://atcoder.jp/login?lang=ja"
session = requests.session()
# ログインページへのアクセス完了
req_before_login = session.get(url_login)

# ログインするための情報を準備する
login_data = {"username": os.environ["USERNAME"], "password": os.environ["PASWORD"]}

# ログインするためにcsrfトークンが必要となるため情報を取得
bs = BeautifulSoup(req_before_login.text, "html.parser")
csrf_token = bs.find(attrs={"name": "csrf_token"}).get("value")
login_data["csrf_token"] = csrf_token

# 2. ログインページで認証を行い、管理者ページへ遷移する
req_after_login = session.post(url_login, data=login_data)
# 3. 認証完了後のページで他ページへ遷移を行う
url = "https://atcoder.jp/contests/arc106/submissions?f.Task=arc106_a&f.LanguageName=&f.Status=AC&f.User=blueberry1001"
req = session.get(url)
soup = BeautifulSoup(req.text, "html.parser")

ac_count = soup.find_all(attrs={ 'class': 'label label-success' })
print(len(ac_count))