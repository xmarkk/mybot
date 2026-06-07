import requests, time, json, re, uuid, os, logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
# ===== CONFIG =====
CHAT_ID = -1003787140439
THREAD_ID = 2
TOKEN = os.getenv("TELEGRAM_TOKEN")

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "schedule.json"

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ===== STATE =====
last_update_id = None
user_state = {}
temp_data = {}
last_sent = {}

# ===== DAY =====
DAY_MAP = {"จ":0,"อ":1,"พ":2,"พฤ":3,"ศ":4,"ส":5,"อา":6}
DAY_FULL_MAP = {
    "จันทร์":0,"อังคาร":1,"พุธ":2,
    "พฤหัส":3,"ศุกร์":4,"เสาร์":5,"อาทิตย์":6
}
DAY_NAME = ["จ","อ","พ","พฤ","ศ","ส","อา"]
DAY_FULL = ["จันทร์","อังคาร","พุธ","พฤหัส","ศุกร์","เสาร์","อาทิตย์"]

# ===== FILE =====
DATA_DIR.mkdir(exist_ok=True)

if not DATA_FILE.exists():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([],f)

try:
    with open(DATA_FILE, encoding="utf-8") as f:
        schedules = json.load(f)
except:
    schedules = []

def save():
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(
            schedules,
            f,
            ensure_ascii=False,
            indent=2
        )

def normalize(s):
    s.setdefault("id",str(uuid.uuid4()))
    s.setdefault("type","once")
    s.setdefault("days",[])
    s.setdefault("user","Unknown")
    s.setdefault("message","")
    s.setdefault("offset",0)
    return s

# ===== VALIDATE =====
def valid_time(t):
    return re.match(
        r"^([01]\d|2[0-3]):([0-5]\d)$",
        t
    )

# ===== PARSE =====
def parse_input(text):

    parts = text.split()

    if len(parts) < 2:
        return None, "❌ รูปแบบไม่ถูกต้อง"

    t = parts[0]

    if not valid_time(t):
        return None, "❌ เวลาไม่ถูกต้อง"

    words = parts[1:]

    offset = 0

    if "พรุ่งนี้" in words:
        offset = 1
        words = [w for w in words if w != "พรุ่งนี้"]

    if "ทุกวัน" in words:
        words = [w for w in words if w != "ทุกวัน"]

        return {
            "time":t,
            "message":" ".join(words),
            "type":"daily",
            "days":[],
            "offset":0
        },None

    days=[]
    i=len(words)-1

    while i>=0:

        w=words[i]

        if w in DAY_MAP:
            days.append(DAY_MAP[w])

        elif w in DAY_FULL_MAP:
            days.append(DAY_FULL_MAP[w])

        else:
            break

        i-=1

    days=sorted(list(set(days)))
    msg_words=words[:i+1]
    msg_join=" ".join(words)

    if "จ-ศ" in msg_join:
        return {
            "time":t,
            "message":" ".join(msg_words),
            "type":"weekly",
            "days":[0,1,2,3,4],
            "offset":0
        },None

    if "ส-อา" in msg_join:
        return {
            "time":t,
            "message":" ".join(msg_words),
            "type":"weekly",
            "days":[5,6],
            "offset":0
        },None

    if days:
        return {
            "time":t,
            "message":" ".join(msg_words),
            "type":"weekly",
            "days":days,
            "offset":0
        },None

    return {
        "time":t,
        "message":" ".join(words),
        "type":"once",
        "days":[],
        "offset":offset
    },None

# ===== UTIL =====
def cut(text,n=18):
    return text[:n]+"..." if len(text)>n else text

def pad(text,w=28):
    return text+" "*(w-len(text) if len(text)<w else 1)

def format_line(s,tag):

    left=f"⏰ {s['time']} {cut(s['message'])}"
    right=f"{tag}   👤 {s['user']}"

    return pad(left)+right

def is_past(s):

    if s["type"]!="once":
        return False

    now=datetime.now()

    target=datetime.strptime(
        s["time"],
        "%H:%M"
    ).replace(
        year=now.year,
        month=now.month,
        day=now.day
    ) + timedelta(days=s.get("offset",0))

    return now > target

# ===== SEND =====
def send(text,markup=None):

    try:

        payload = {
            "chat_id":CHAT_ID,
            "text":text,
            "message_thread_id":THREAD_ID
        }

        if markup:
            payload["reply_markup"] = markup

        res = requests.post(
            f"{BASE_URL}/sendMessage",
            json=payload,
            timeout=15
        )

        if res.status_code != 200:
            logging.error(res.text)

    except Exception as e:

        logging.error(
            f"Send Error: {e}"
        )

# ===== INLINE =====
def build_inline(action):

    buttons=[]

    for s in sorted(
        schedules,
        key=lambda x:x["time"]
    ):

        if is_past(s):
            continue

        tag="🔁 ทุกวัน" if s["type"]=="daily" else "⏰ วันนี้"

        buttons.append([{
            "text":format_line(s,tag),
            "callback_data":f"{action}|{s['id']}"
        }])

    return {
        "inline_keyboard":buttons
    } if buttons else None

# ===== UI =====
def build_ui():

    now=datetime.now()
    wd=now.weekday()

    today=[]
    tmr=[]
    daily=[]
    weekly=[]

    for s in schedules:

        s=normalize(s)

        if is_past(s):
            continue

        if s["type"]=="daily":

            daily.append(s)

        elif s["type"]=="weekly":

            if wd in s["days"]:
                today.append(s)
            else:
                weekly.append(s)

        else:

            if s.get("offset",0)==1:
                tmr.append(s)
            else:
                today.append(s)

    def sort(x):
        return sorted(
            x,
            key=lambda a:a["time"]
        )

    msg="📋 ตารางแจ้งเตือน\n\n"

    if today:

        msg+=f"🟢 วันนี้ ({DAY_FULL[wd]})\n"

        for s in sort(today):

            tag="🔁 ทุกวัน" if s["type"]=="daily" else "⏰ ครั้งเดียว"

            msg+=format_line(s,tag)+"\n"

        msg+="\n"

    if tmr:

        msg+=f"🔵 พรุ่งนี้ ({DAY_FULL[(wd+1)%7]})\n"

        for s in sort(tmr):
            msg+=format_line(s,"⏰ ครั้งเดียว")+"\n"

        msg+="\n"

    if daily:

        msg+="🔁 ทุกวัน\n"

        for s in sort(daily):
            msg+=format_line(s,"")+" \n"

        msg+="\n"

    if weekly:

        msg+="📅 เฉพาะวัน\n"

        for s in sort(weekly):

            d=" ".join([
                DAY_NAME[x]
                for x in s["days"]
            ])

            msg+=format_line(s,f"({d})")+"\n"

    return msg.strip()

# ===== SCHEDULER =====
def run_scheduler():

    global schedules

    now=datetime.now()
    wd=now.weekday()

    new=[]

    logging.info(
        f"Scheduler tick {now.strftime('%H:%M:%S')}"
    )

    for s in schedules:

        s=normalize(s)

        target=datetime.strptime(
            s["time"],
            "%H:%M"
        ).replace(
            year=now.year,
            month=now.month,
            day=now.day
        ) + timedelta(days=s.get("offset",0))

        diff=(now-target).total_seconds()

        should_run=(
            s["type"]=="daily" or
            (
                s["type"]=="weekly"
                and wd in s["days"]
            ) or
            s["type"]=="once"
        )

        if should_run and 0 <= diff < 60:

            key=f"{s['id']}_{target.date()}"

            if last_sent.get(key)!=True:

                logging.info(
                    f"Sending alert: {s['message']}"
                )

                send(
                    f"⏰ {s['time']} {s['message']}"
                )

                last_sent[key]=True

        if s["type"]=="once" and diff > 300:
            continue

        new.append(s)

    schedules=new
    save()

# ===== HANDLE =====
def handle(msg):

    text=msg.get("text","")

    user=msg.get("from",{})

    uid=user.get("id")

    name=user.get(
        "first_name",
        "User"
    )

    if text=="➕ เพิ่ม":

        user_state[uid]="add"

        send(
            "➕ เพิ่ม\n"
            "18:00 กินข้าว / ทุกวัน / จ-ศ / พรุ่งนี้"
        )

        return

    if user_state.get(uid)=="add":

        data,err=parse_input(text)

        if err:
            send(err)
            return

        now=datetime.now()

        if data["type"]=="once":

            target=datetime.strptime(
                data["time"],
                "%H:%M"
            ).replace(
                year=now.year,
                month=now.month,
                day=now.day
            ) + timedelta(
                days=data.get("offset",0)
            )

            if target < now:

                send(
                    "❌ เวลานี้ผ่านมาแล้ว "
                    "ลองตั้งเวลาใหม่"
                )

                return

        schedules.append({
            "id":str(uuid.uuid4()),
            "time":data["time"],
            "message":data["message"],
            "type":data["type"],
            "days":data["days"],
            "offset":data.get("offset",0),
            "user":name
        })

        save()

        send("✅ เพิ่มแล้ว")

        user_state[uid]=None

        return

    if text=="📋 ดูทั้งหมด":
        send(build_ui())
        return

    if text=="🗑 ลบ":
        send("🗑 เลือก",build_inline("del"))
        return

    if text=="✏️ แก้ไข":
        send("✏️ เลือก",build_inline("edit"))
        return

    if user_state.get(uid)=="edit_input":

        sid=temp_data.get(uid)

        for s in schedules:

            if s["id"]==sid:
                s["message"]=text

        save()

        send("✏️ แก้ไขแล้ว")

        user_state[uid]=None

# ===== CALLBACK =====
def handle_callback(q):

    data=q.get("data")

    uid=q.get(
        "from",
        {}
    ).get("id")

    if not data or "|" not in data:
        return

    action,sid=data.split("|")

    global schedules

    if action=="del":

        schedules=[
            s for s in schedules
            if s["id"]!=sid
        ]

        save()

        send("🗑 ลบแล้ว")

    elif action=="edit":

        temp_data[uid]=sid

        user_state[uid]="edit_input"

        send("✏️ พิมพ์ข้อความใหม่:")

# ===== STARTUP =====
logging.info("TimeBot Started")

# ===== LOOP =====
while True:

    try:

        run_scheduler()

        params={"timeout":5}

        if last_update_id:
            params["offset"]=last_update_id+1

        res=requests.get(
            f"{BASE_URL}/getUpdates",
            params=params,
            timeout=15
        ).json()

        for u in res.get("result",[]):

            last_update_id=u["update_id"]

            if "callback_query" in u:

                handle_callback(
                    u["callback_query"]
                )

                continue

            if "message" not in u:
                continue

            msg=u["message"]

            if msg.get(
                "message_thread_id"
            )!=THREAD_ID:
                continue

            handle(msg)

        time.sleep(1)

    except Exception as e:

        logging.error(
            f"Main Loop Error: {e}"
        )

        time.sleep(2)
