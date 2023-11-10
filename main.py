import json
import os
import time
from urllib import request
import requests
from bs4 import BeautifulSoup
import asyncio
from collections import deque
import shoujin

users = shoujin.json_.load_user_data()
shoujin.time.save(time.time())
def update_score():
    shoujin.main.update()
    submissions = asyncio.run(shoujin.get.submission_data(users))
    for submission in submissions:
        point = asyncio.run(shoujin.get.point(submission))
        users[submission.user_id].score += point
        print(f"{submission.user_id} get {point} point!")
    shoujin.json_.save_user_data(users)
#GitHubに保存
def pushGitHub():
    os.system('git add .')
    os.system(f'git config --global user.email "{os.environ["EMAIL"]}"')
    os.system('git config --global user.name "strawberry29"')
    os.system('git commit -m "update"')
    os.system('git push origin main')
pushGitHub()


