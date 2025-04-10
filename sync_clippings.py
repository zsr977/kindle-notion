import os
import requests
import re
from typing import List, Dict
from datetime import datetime
import pytz  # 用于处理时区

NOTION_TOKEN = "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"
NOTION_DATABASE_ID = "1d0b7f6b184c80eb99bdc23049a72cf4"
CLIPPINGS_FILE = "MyClippings.txt"
SYNCED_LOG = "synced.log"  # 用于记录已同步的笔记避免重复

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 正则表达式，用于提取位置和时间
location_pattern = r"位置 #(\d+-\d+)"
time_pattern = r"添加于\s+([\d]{4}年[\d]{1,2}月[\d]{1,2}日星期[\u4e00-\u9fa5]+\s+(上午|下午)?\d{1,2}:\d{2}:\d{2})"
weekday_pattern = r"星期[一-七]"

def parse_clippings(file_path: str) -> List[Dict]:
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    entries = content.strip().split("==========")
    notes = []

    for entry in entries:
        lines = [line.strip() for line in entry.strip().split('\n') if line.strip()]
        if len(lines) < 3:
            continue

        title = lines[0]
        meta = lines[1]
        content = "\n".join(lines[2:])

        author = ""
        if "(" in title and ")" in title:
            title_parts = title.rsplit("(", 1)
            title_parts1 = title_parts[0].split("（")
            title = title_parts1[0].strip()
            author = title_parts[1].replace(")", "").strip()

        location_match = re.search(location_pattern, meta)
        location = location_match.group(1) if location_match else ""

        time_match = re.search(time_pattern, meta)
        time_str = time_match.group(1) if time_match else ""

        time = convert_to_iso_format(time_str)

        notes.append({
            "title": title,
            "author": author,
            "location": location,
            "content": content,
            "time": time
        })

    return notes

def convert_to_iso_format(time_str: str) -> str:
    try:
        if not time_str:
            return ""

        # 去除“星期”部分，并确保去掉多余空格
        time_str = re.sub(r"星期[一二三四五六七]", "", time_str).strip()

        # 正则匹配时间部分，考虑上午/下午时间转换
        match = re.search(r"(上午|下午)?(\d{1,2}):(\d{2}):(\d{2})", time_str)
        if match:
            period = match.group(1)
            hour = int(match.group(2))
            minute = match.group(3)
            second = match.group(4)

            # 处理上午下午的时间转换
            if period == "下午" and hour < 12:
                hour += 12  # 下午1点到12点转换为13到23
            if period == "上午" and hour == 12:
                hour = 0  # 上午12点转换为0点

            # 格式化为24小时制时间
            time_24h = f"{hour:02}:{minute}:{second}"
            time_str = re.sub(r"(上午|下午)?\d{1,2}:\d{2}:\d{2}", time_24h, time_str)

        # 如果没有找到明确的时间，使用默认的时间
        if not re.search(r"\d{2}:\d{2}:\d{2}", time_str):
            time_str += " 12:00:00"

        # 解析为 datetime 对象
        naive_dt = datetime.strptime(time_str, "%Y年%m月%d日 %H:%M:%S")
        beijing = pytz.timezone("Asia/Shanghai")
        local_dt = beijing.localize(naive_dt)
        utc_dt = local_dt.astimezone(pytz.utc)

        # 返回 UTC 时间的 ISO 格式
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    except Exception as e:
        print(f"⚠️ 无法解析时间字符串: '{time_str}'，错误: {e}")
        return ""

def is_already_synced(note_hash: str) -> bool:
    if not os.path.exists(SYNCED_LOG):
        return False
    with open(SYNCED_LOG, 'r') as f:
        return note_hash in f.read()

def mark_as_synced(note_hash: str):
    with open(SYNCED_LOG, 'a') as f:
        f.write(note_hash + '\n')

def upload_to_notion(note: Dict):
    data = {
        "parent": { "database_id": NOTION_DATABASE_ID },
        "properties": {
            "Name": {
                "title": [
                    { "text": { "content": note["title"] } }
                ]
            },
            "作者": {
                "rich_text": [
                    { "text": { "content": note["author"] } }
                ]
            },
            "位置": {
                "rich_text": [
                    { "text": { "content": note["location"] } }
                ]
            },
            "笔记内容": {
                "rich_text": [
                    { "text": { "content": note["content"] } }
                ]
            },
            "时间": {
                "date": {
                    "start": note["time"]
                }
            }
        }
    }
    response = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=data)
    if response.status_code != 200:
        print(f"❌ 上传失败：{response.text}")
    else:
        print(f"✅ 成功上传《{note['title']}》的笔记")

def main():
    notes = parse_clippings(CLIPPINGS_FILE)
    for note in notes:
        note_hash = f"{note['title']}_{note['location']}".replace(" ", "_")
        if is_already_synced(note_hash):
            continue
        upload_to_notion(note)
        mark_as_synced(note_hash)

if __name__ == "__main__":
    main()
