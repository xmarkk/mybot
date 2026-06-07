import requests

from bs4 import BeautifulSoup

import json

import os

import time

import logging

from pathlib import Path

from dotenv import load_dotenv

# =========================

# LOAD ENV

# =========================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID = -1003787140439
THREAD_ID = 26

URL = "https://www.nkp-hospital.go.th/th/nkpNews2.php"

# =========================
# PATH
# =========================
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

STATE_FILE = DATA_DIR / "seen_news.json"

CHECK_INTERVAL = 600  # 600 วินาที = 10 นาที

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =========================
# REQUEST SESSION
# =========================
session = requests.Session()

# =========================
# TELEGRAM
# =========================
def send_message(text):

    try:
        response = session.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "message_thread_id": THREAD_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            },
            timeout=15
        )

        if response.status_code != 200:
            logging.error(response.text)

    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# =========================
# LOAD SAVED POSTS
# =========================
def load_seen():

    if not os.path.exists(STATE_FILE):
        return []

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:
        return []

# =========================
# SAVE POSTS
# =========================
def save_seen(data):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

# =========================
# FETCH NEWS
# =========================
def fetch_news():

    try:

        response = session.get(
            URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
            timeout=20
        )

        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        news_list = []

        keywords = [
            "รับสมัคร",
            "ประกาศ",
            "ผู้มีสิทธิ",
            "คัดเลือก",
            "สอบ",
            "พนักงาน",
            "ลูกจ้าง"
        ]

        for row in soup.select("table tr"):

            link = row.find("a", href=True)

            cells = row.find_all("td")

            if not link or len(cells) < 3:
                continue

            title = link.text.strip()

            # กรองเฉพาะข่าวเกี่ยวกับงาน
            if not any(
                k in title
                for k in keywords
            ):
                continue

            href = link["href"].lstrip("./")

            full_url = (
                "https://www.nkp-hospital.go.th/th/"
                + href
            )

            news_date = cells[-1].text.strip()

            news_list.append({
                "title": title,
                "url": full_url,
                "date": news_date
            })

        # DEBUG
        print(f"Found {len(news_list)} matching posts")

        # เอาแค่ 5 ข่าวล่าสุด
        return news_list[:5]

    except Exception as e:

        logging.error(
            f"Fetch Error: {e}"
        )

        return []

# =========================
# FORMAT MESSAGE
# =========================
def format_message(item):

    return (
        "🏥 <b>พบประกาศใหม่</b>\n\n"
        f"📌 <b>{item['title']}</b>\n\n"
        f"📅 {item['date']}\n\n"
        f"🔗 <a href='{item['url']}'>กดเพื่อเปิดประกาศ</a>"
    )

# =========================
# CHECK NEWS
# =========================
def check_news():

    logging.info(
        "Checking website..."
    )

    latest_news = fetch_news()

    if not latest_news:

        logging.warning(
            "No data fetched"
        )

        return

    seen = load_seen()

    seen_urls = {
        item["url"]
        for item in seen
    }

    new_posts = [
        item
        for item in latest_news
        if item["url"] not in seen_urls
    ]

    if not new_posts:

        logging.info(
            "No new posts"
        )

        return

    logging.info(
        f"Found {len(new_posts)} new posts"
    )

    # ส่งจากเก่า -> ใหม่
    for item in reversed(new_posts):

        send_message(
            format_message(item)
        )

        logging.info(
            f"Sent: {item['title']}"
        )

        time.sleep(2)

    # บันทึกข่าวล่าสุด
    save_seen(latest_news)

# =========================
# STARTUP
# =========================
def startup():

    send_message(
        "🤖 <b>NKP Monitor เริ่มทำงานแล้ว</b>\n"
        "⏰ ตรวจเว็บทุก 10 นาที"
    )

# =========================
# MAIN
# =========================
def main():

    startup()

    while True:

        try:

            check_news()

            time.sleep(
                CHECK_INTERVAL
            )

        except KeyboardInterrupt:

            logging.info(
                "Bot stopped"
            )

            break

        except Exception as e:

            logging.error(
                f"Main Loop Error: {e}"
            )

            time.sleep(30)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
