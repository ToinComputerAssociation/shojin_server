import os
import time
import asyncio
from collections import deque

def pushGitHub():
    os.system('git add .')
    os.system(f'git config --global user.email "{os.environ["EMAIL"]}"')
    os.system('git config --global user.name "strawberry29"')
    os.system('git commit -m "update"')
    os.system('git push origin main')

pushGitHub()


