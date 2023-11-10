from urllib import request
import requests
from bs4 import BeautifulSoup
import os
import shoujin
import json
import asyncio
users = {}
b = shoujin.user("blueberry1001", "blueberry")
b.score = 0
users = shoujin.json_.load_user_data()
users[b.id] = b
shoujin.main.init()
submissions = asyncio.run(shoujin.get.submission_data(users))
for submission in submissions:
    point = asyncio.run(shoujin.get.point(submission))
    users[submission.user_id].score += point
    print(f"{submission.user_id} get {point} point!")
shoujin.json_.save_user_data(users)
