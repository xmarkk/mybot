import requests
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ===== LOAD ENV =====

load_dotenv()
# ===== CONFIG =====

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = -1003787140439
THREAD_ID = 5
API_KEY = "0b4cc4d5360bbdfba5dfd1113b7043ea"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# ===== BASE PATH =====
BASE_DIR = Path(__file__).resolve().parent.parent
last_update_id = None
last_rain_alert = {}
# กันยิงซ้ำ
last_report_sent = {
    "morning": None,
    "evening": None
}

# ===== CITY =====
city_map = {
    "จอมทอง": "Chom Thong",
    "เชียงใหม่": "Chiang Mai",
    "ลำพูน": "Lamphun",
    "🌸 จอมทอง": "Chom Thong",
    "🌷 เชียงใหม่": "Chiang Mai",
    "🌼 ลำพูน": "Lamphun"
}

cities = ["Chiang Mai", "Chom Thong", "Lamphun"]

city_coords = {
    "Chom Thong": (18.417, 98.674),
    "Chiang Mai": (18.788, 98.985),
    "Lamphun": (18.580, 99.007)
}

# ===== MENU =====
def get_menu_keyboard():
    return {
        "keyboard": [
            ["🌸 จอมทอง", "🌷 เชียงใหม่"],
            ["🌼 ลำพูน", "🌤 ดูทั้งหมด"]
        ],
        "resize_keyboard": True
    }

# ===== SEND =====
def send_message(text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "message_thread_id": THREAD_ID,
            "reply_markup": get_menu_keyboard()
        }, timeout=10)
    except:
        pass

# ===== WEATHER =====
def get_weather(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=th"
        data = requests.get(url, timeout=10).json()
        if "main" not in data:
            return None
        return data["main"]["temp"], data["weather"][0]["description"]
    except:
        return None

# ===== RAIN =====
def get_rain_chance(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang=th"
        data = requests.get(url, timeout=10).json()

        if "list" not in data:
            return None

        for item in data["list"][:3]:
            pop = item.get("pop")
            if pop is not None:
                return int(pop * 100)

        return 0
    except:
        return None

# ===== AIR =====
def get_air_quality(city):
    try:
        lat, lon = city_coords[city]
        url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        data = requests.get(url, timeout=10).json()
        return data["list"][0]["components"]["pm2_5"]
    except:
        return None

# ===== LEVEL =====
def pm_level(pm25):
    if pm25 >= 40: return "🔴 แย่"
    elif pm25 >= 26: return "🟠 เริ่มมีผล"
    elif pm25 >= 16: return "🟡 ปานกลาง"
    else: return "🟢 ดี"

def rain_level(rain):
    if rain >= 85: return "⛈ ฝนหนักแน่นอน"
    elif rain >= 70: return "☔ ฝนกำลังมา"
    elif rain >= 40: return "🌦 มีโอกาสตก"
    else: return "☁️ ฝนเล็กน้อย"

# ===== FORMAT =====
def format_weather_block(city):
    weather = get_weather(city)
    rain = get_rain_chance(city)
    pm25 = get_air_quality(city)

    if not weather:
        return f"📍 {city}\n❌ ไม่พบข้อมูล"

    temp, _ = weather
    rain_text = f"{rain}%" if rain is not None else "?"

    msg = f"📍 {city}\n🌡 {temp:.1f}°C 🌧 {rain_text}"

    if pm25 is not None:
        msg += f"\n🌫 {pm25:.0f} µg/m³ {pm_level(pm25)}"

    return msg

# ===== REPORT =====
def send_weather_report(title=""):
    msg = f"{title}🌸 รายงานอากาศ\n\n"

    for c in cities:
        msg += format_weather_block(c) + "\n\n"

    send_message(msg.strip())

# ===== ⏰ AUTO REPORT =====
def check_scheduled_report():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    today = now.date()

    # 🌅 เช้า
    if current_time == "07:00":
        if last_report_sent["morning"] != today:
            send_weather_report("🌅 ")
            last_report_sent["morning"] = today

    # 🌆 เย็น
    if current_time == "18:00":
        if last_report_sent["evening"] != today:
            send_weather_report("🌆 ")
            last_report_sent["evening"] = today

# ===== RAIN ALERT =====
def check_rain_alert():
    alerts = []
    now = datetime.now()

    for city in cities:
        rain = get_rain_chance(city)

        if rain is None or rain < 60:
            continue

        last_time = last_rain_alert.get(city)
        if last_time and now - last_time < timedelta(hours=3):
            continue

        alerts.append(f"📍 {city} 🌧 {rain}% {rain_level(rain)}")
        last_rain_alert[city] = now

    if alerts:
        send_message("🌧 แจ้งเตือนฝน\n" + "\n".join(alerts))

# ===== MESSAGE =====
def check_messages():
    global last_update_id

    params = {"timeout": 5}
    if last_update_id:
        params["offset"] = last_update_id + 1

    try:
        res = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=10).json()
    except:
        return

    for update in res.get("result", []):
        last_update_id = update["update_id"]

        if "message" not in update:
            continue

        msg = update["message"]

        if msg.get("message_thread_id") != THREAD_ID:
            continue

        text = msg.get("text", "").strip()

        if text == "🌤 ดูทั้งหมด":
            send_weather_report()
            continue

        city = city_map.get(text)
        if city:
            send_message(format_weather_block(city))

# ===== START =====
send_message("🌸 WeatherBot พร้อมใช้งาน")

# ===== LOOP =====
last_rain_check = 0

while True:
    try:
        check_messages()
        check_scheduled_report()

        now = time.time()

        if now - last_rain_check > 900:
            check_rain_alert()
            last_rain_check = now

        time.sleep(1)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(3)
