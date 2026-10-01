import os
import sys

import django

cur_path = os.path.abspath(__file__)
parent = os.path.dirname
sys.path.append(parent(parent(cur_path)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

if __name__ == "__main__":
    print("Claude 网页会话不支持自动刷新；已跳过旧令牌维护任务。")

