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
    print("❌ TOKEN NOT FOUND")
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

tracked_accounts = load_data()

# ================= USERNAME PARSER =================
def extract_username(text):
    match = re.search(r"(?:instagram\.com/)?@?([a-zA-Z0-9._]+)", text)
    return match.group(1).lower() if match else None

# ================= INSTAGRAM CHECK =================
def check_account(username):
    try:
        url = f"https://www.instagram.com/{username}/"
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 404:
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

    except:
        return {"status": "error"}

# ================= TILE UI =================
def create_card(username, followers, status, profile_pic=None):
    width, height = 800, 250
    img = Image.new("RGB", (width, height), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("Poppins-Bold.ttf", 44)
        text_font = ImageFont.truetype("Poppins-Regular.ttf", 26)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # Profile Pic
    try:
        if profile_pic:
            response = requests.get(profile_pic, timeout=5)
            pfp = Image.open(BytesIO(response.content)).resize((110, 110)).convert("RGB")

            mask = Image.new("L", (110, 110), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, 110, 110), fill=255)

            img.paste(pfp, (30, 70), mask)
        else:
            draw.ellipse((30, 70, 140, 180), fill=(60, 60, 80))
    except:
        draw.ellipse((30, 70, 140, 180), fill=(60, 60, 80))

    # Username
    draw.text((180, 60), username, font=title_font, fill=(255, 255, 255))

    # Followers
    followers_text = f"{followers} followers" if followers else "Followers: --"
    draw.text((180, 120), followers_text, font=text_font, fill=(180, 180, 180))

    # Status badge
    if status == "ACTIVE":
        color = (0, 200, 255)
    else:
        color = (255, 180, 0)

    draw.rectangle((180, 160, 340, 200), fill=color)
    draw.text((190, 165), status, font=text_font, fill=(0, 0, 0))

    return img

async def send_card(channel, username, followers, status, profile_pic=None):
    img = create_card(username, followers, status, profile_pic)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(buffer, filename="card.png")
    await channel.send(file=file)

# ================= MONITOR LOOP =================
async def monitor_accounts():
    await client.wait_until_ready()

    while not client.is_closed():
        for username in tracked_accounts:
            result = check_account(username)

            tracked_accounts[username]["status"] = result["status"]
            tracked_accounts[username]["last_checked"] = str(datetime.now())

        save_data(tracked_accounts)
        await asyncio.sleep(60)

# ================= CLIENT =================
class Bot(discord.Client):
    async def setup_hook(self):
        self.loop.create_task(monitor_accounts())

client = Bot(intents=intents)

# ================= EVENTS =================
@client.event
async def on_ready():
    print(f"✅ Bot running as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    username = extract_username(message.content)
    if not username:
        return

    # prevent duplicate spam
    if username in tracked_accounts:
        await message.channel.send(f"⚠️ Already tracking @{username}")
        return

    result = check_account(username)

    if result["status"] == "active":
        await send_card(
            message.channel,
            username,
            result.get("followers"),
            "ACTIVE",
            result.get("profile_pic")
        )
    else:
        await send_card(
            message.channel,
            username,
            None,
            "MONITORING",
            None
        )

    tracked_accounts[username] = {
        "status": result["status"],
        "added_at": str(datetime.now())
    }

    save_data(tracked_accounts)

# ================= START =================
client.run(TOKEN)
