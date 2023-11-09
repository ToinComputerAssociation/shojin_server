from urllib import request
import requests
from bs4 import BeautifulSoup
import os
import shoujin
import json
import asyncio
users = {}
b = shoujin.user("strawberry0929", "strawberry")
b.score = 100
users["strawberry0929"] = b
users = shoujin.json_.load_user_data()
shoujin.init.all()
submissions = asyncio.run(shoujin.get.submission_data(users))
print([submission.user_id for submission in submissions])
