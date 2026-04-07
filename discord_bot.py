import discord
import requests
import asyncio
import os
import re
import json
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
DATA_FILE = "data.json"

if not TOKEN:
    print("TOKEN missing")
    exit()

intents = discord.Intents.default()
intents.message_content = True

# ================= STORAGE =================
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

tracked = load_data()

# ================= USERNAME =================
def extract_username(text):
    match = re.search(r"(?:instagram\.com/)?@?([a-zA-Z0-9._]+)", text)
    return match.group(1).lower() if match else None

# ================= INSTAGRAM CHECK =================
def check_account(username):
    try:
        url = f"https://www.instagram.com/{username}/"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        }

        r = requests.get(url, headers=headers, timeout=10)

        # 🔥 REAL DETECTION
        if "Sorry, this page isn't available" in r.text:
            return {"status": "banned"}

        if r.status_code == 200:
            html = r.text

            # followers (optional)
            followers_match = re.search(r'"edge_followed_by":{"count":(\d+)}', html)
            followers = int(followers_match.group(1)) if followers_match else None

            # profile pic (optional)
            pic_match = re.search(r'"profile_pic_url_hd":"([^"]+)"', html)
            profile_pic = pic_match.group(1).replace("\\u0026", "&") if pic_match else None

            return {
                "status": "active",
                "followers": followers,
                "profile_pic": profile_pic
            }

        return {"status": "error"}

    except Exception as e:
        print("ERROR:", e)
        return {"status": "error"}

# ================= TILE =================
def create_card(username, followers, status, profile_pic=None):
    img = Image.new("RGB", (800, 250), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    try:
        title = ImageFont.truetype("Poppins-Bold.ttf", 44)
        text = ImageFont.truetype("Poppins-Regular.ttf", 26)
    except:
        title = ImageFont.load_default()
        text = ImageFont.load_default()

    # profile pic
    try:
        if profile_pic:
            p = requests.get(profile_pic, timeout=5)
            pfp = Image.open(BytesIO(p.content)).resize((110, 110)).convert("RGB")

            mask = Image.new("L", (110, 110), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 110, 110), fill=255)

            img.paste(pfp, (30, 70), mask)
        else:
            draw.ellipse((30, 70, 140, 180), fill=(60, 60, 80))
    except:
        draw.ellipse((30, 70, 140, 180), fill=(60, 60, 80))

    # username
    draw.text((180, 60), username, font=title, fill=(255, 255, 255))

    # followers
    f_text = f"{followers} followers" if followers else "Followers: --"
    draw.text((180, 120), f_text, font=text, fill=(180, 180, 180))

    # status
    color = (0, 200, 255) if status == "ACTIVE" else (255, 180, 0)
    draw.rectangle((180, 160, 340, 200), fill=color)
    draw.text((190, 165), status, font=text, fill=(0, 0, 0))

    return img

async def send_card(channel, username, followers, status, profile_pic):
    img = create_card(username, followers, status, profile_pic)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    await channel.send(file=discord.File(buf, "card.png"))

# ================= MONITOR =================
async def monitor():
    await client.wait_until_ready()

    while True:
        for u in tracked:
            res = check_account(u)

            tracked[u]["status"] = res["status"]
            tracked[u]["last_check"] = str(datetime.now())

        save_data(tracked)
        await asyncio.sleep(60)

# ================= CLIENT =================
class Bot(discord.Client):
    async def setup_hook(self):
        self.loop.create_task(monitor())

client = Bot(intents=intents)

# ================= EVENTS =================
@client.event
async def on_ready():
    print("BOT READY")

@client.event
async def on_message(msg):
    if msg.author == client.user:
        return

    username = extract_username(msg.content)
    if not username:
        return

    # prevent spam
    if username in tracked:
        await msg.channel.send(f"Already tracking @{username}")
        return

    res = check_account(username)

    # 🔥 FIXED LOGIC
    if res["status"] == "banned":
        status = "MONITORING"
        followers = None
        pic = None
    else:
        status = "ACTIVE"
        followers = res.get("followers")
        pic = res.get("profile_pic")

    await send_card(msg.channel, username, followers, status, pic)

    tracked[username] = {
        "status": res["status"],
        "added": str(datetime.now())
    }

    save_data(tracked)

# ================= START =================
client.run(TOKEN)
