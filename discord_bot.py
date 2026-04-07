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
            "Accept-Language": "en-US,en;q=0.9",
        }

        r = requests.get(url, headers=headers, timeout=10)

        # banned detection
        if "Sorry, this page isn't available" in r.text:
            return {"status": "banned"}

        if r.status_code == 200:
            html = r.text

            # followers
            followers_match = re.search(r'"count":(\d+),"edge_followed_by"', html)
            followers = int(followers_match.group(1)) if followers_match else None

            # profile pic
            pic_match = re.search(r'"profile_pic_url":"([^"]+)"', html)
            profile_pic = pic_match.group(1).replace("\\u0026", "&") if pic_match else None

            return {
                "status": "active",
                "followers": followers,
                "profile_pic": profile_pic
            }

        return {"status": "error"}

    except:
        return {"status": "error"}

# ================= CARD =================
def create_card(username, followers, status, profile_pic=None, time_taken=None):
    img = Image.new("RGB", (820, 260), (12, 12, 22))
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
    draw.text((180, 50), username, font=title, fill=(255, 255, 255))

    # followers
    f_text = f"{followers} followers" if followers else "Followers: --"
    draw.text((180, 110), f_text, font=text, fill=(180, 180, 180))

    # time
    if time_taken is not None:
        draw.text((180, 150), f"Time: {time_taken}s", font=text, fill=(120, 120, 120))

    # status
    color = (0, 200, 255) if status == "ACTIVE" else (255, 180, 0)
    draw.rectangle((180, 190, 340, 230), fill=color)
    draw.text((190, 195), status, font=text, fill=(0, 0, 0))

    return img

async def send_card(channel, username, followers, status, profile_pic, time_taken):
    img = create_card(username, followers, status, profile_pic, time_taken)

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

    if username in tracked:
        await msg.channel.send(f"Already tracking @{username}")
        return

    start = datetime.now()
    res = check_account(username)
    end = datetime.now()

    time_taken = round((end - start).total_seconds(), 2)

    if res["status"] == "banned":
        status = "MONITORING"
        followers = None
        pic = None
    else:
        status = "ACTIVE"
        followers = res.get("followers")
        pic = res.get("profile_pic")

    await send_card(msg.channel, username, followers, status, pic, time_taken)

    tracked[username] = {
        "status": res["status"],
        "added": str(datetime.now())
    }

    save_data(tracked)

# ================= START =================
client.run(TOKEN)
