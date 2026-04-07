import discord
import requests
import asyncio
import os
import re
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

TOKEN = os.getenv("TOKEN")

tracked_accounts = {}
user_cache = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ---------------- TIME FORMAT ----------------
def format_time(seconds):
    seconds = int(seconds)

    if seconds < 1:
        return "1s"
    elif seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds//60}m {seconds%60}s"
    else:
        return f"{seconds//3600}h {(seconds%3600)//60}m"

# ---------------- USERNAME ----------------
def extract_username(text):
    text = text.strip()
    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", text)
    if match:
        return match.group(1)
    return text.replace("@", "")

# ---------------- INSTAGRAM CHECK ----------------
def check_instagram(username):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "x-ig-app-id": "936619743392459"
    }

    # TRY API
    for _ in range(2):
        try:
            r = requests.get(
                f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
                headers=headers,
                timeout=10
            )

            if r.status_code == 200:
                data = r.json()
                if data.get("data") and data["data"]["user"]:
                    user = data["data"]["user"]
                    return "ACTIVE", user["edge_followed_by"]["count"], user["profile_pic_url_hd"]
        except:
            continue

    # WEBSITE CHECK
    try:
        r = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=10)
        html = r.text.lower()

        if "sorry, this page isn't available" in html:
            return "BANNED", None, None

        if "followers" in html:
            return "ACTIVE", None, None

    except:
        pass

    return "UNKNOWN", None, None

# ---------------- CARD ----------------
def generate_card(username, followers, time_text, pic_url, status):

    base = os.path.dirname(os.path.abspath(__file__))

    font_title = ImageFont.truetype(os.path.join(base, "Poppins-Bold.ttf"), 42)
    font_stats = ImageFont.truetype(os.path.join(base, "Poppins-Regular.ttf"), 28)
    font_small = ImageFont.truetype(os.path.join(base, "Poppins-Regular.ttf"), 26)

    W, H = 1000, 340
    img = Image.new("RGB", (W, H), (24, 24, 28))
    draw = ImageDraw.Draw(img)

    # COLORS
    if status == "ACTIVE":
        color = (0, 180, 255)
        label = "ACTIVE"
    elif status == "MONITORING":
        color = (255, 170, 0)
        label = "MONITORING"
    else:
        color = (0, 220, 120)
        label = "RECOVERED"

    # AVATAR
    av_size = 150
    av_x, av_y = 40, (H - av_size) // 2

    draw.ellipse((av_x, av_y, av_x+av_size, av_y+av_size), fill=(60,60,70))

    if pic_url:
        try:
            r = requests.get(pic_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            pfp = Image.open(BytesIO(r.content)).convert("RGBA").resize((av_size, av_size))

            mask = Image.new("L", (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0,0,av_size,av_size), fill=255)

            img.paste(pfp, (av_x, av_y), mask)
        except:
            pass

    # TEXT
    tx = av_x + av_size + 40

    draw.text((tx, 40), username, fill=(255,255,255), font=font_title)

    followers = followers if followers else 0
    draw.text((tx, 110), f"{followers:,} followers", fill=(200,200,200), font=font_stats)

    # STATUS
    draw.rectangle((tx, 150, tx+220, 190), fill=color)
    draw.text((tx+20, 155), label, fill=(0,0,0), font=font_small)

    # 🔥 TIME FIXED (BIG + CLEAR)
    draw.text((tx, 210), f"Time Taken: {time_text}", fill=(255,255,255), font=font_small)

    draw.text((tx, 250), f"instagram.com/{username}", fill=(140,140,160), font=font_small)

    path = "card.png"
    img.save(path)
    return path

# ---------------- MONITOR ----------------
async def monitor():
    await client.wait_until_ready()

    while True:
        for username in list(tracked_accounts):

            status, followers, pic = check_instagram(username)

            if status == "ACTIVE":
                data = tracked_accounts[username]

                diff = datetime.now(timezone.utc) - data["time"]
                time_text = format_time(diff.total_seconds())

                if followers is None and username in user_cache:
                    followers = user_cache[username]["followers"]
                    pic = user_cache[username]["pic"]

                card = generate_card(username, followers, time_text, pic, "RECOVERED")

                await data["channel"].send(
                    content=f"🔥 ACCOUNT RECOVERED | @{username}",
                    file=discord.File(card)
                )

                del tracked_accounts[username]

        await asyncio.sleep(60)

# ---------------- EVENTS ----------------
@client.event
async def on_ready():
    print(f"Bot running as {client.user}")
    client.loop.create_task(monitor())

@client.event
async def on_message(message):

    if message.author == client.user:
        return

    text = message.content.strip()

    if not text.startswith("!"):
        return

    inputs = text[1:].split()

    for raw in inputs:

        username = extract_username(raw)
        if not username:
            continue

        start = datetime.now(timezone.utc)

        status, followers, pic = check_instagram(username)

        print(f"[DEBUG] {username} → {status}")

        # ACTIVE
        if status == "ACTIVE":

            if followers and pic:
                user_cache[username] = {
                    "followers": followers,
                    "pic": pic
                }

            if followers is None and username in user_cache:
                followers = user_cache[username]["followers"]
                pic = user_cache[username]["pic"]

            if username in tracked_accounts:
                del tracked_accounts[username]

            elapsed = format_time((datetime.now(timezone.utc) - start).total_seconds())

            card = generate_card(username, followers, elapsed, pic, "ACTIVE")

            await message.channel.send(
                content=f"✅ ACCOUNT ACTIVE | @{username}",
                file=discord.File(card)
            )

        # MONITORING (BANNED + UNKNOWN)
        else:

            if username not in tracked_accounts:
                tracked_accounts[username] = {
                    "channel": message.channel,
                    "time": datetime.now(timezone.utc)
                }

                card = generate_card(username, 0, "Scanning...", None, "MONITORING")

                await message.channel.send(
                    content=f"🛰️ MONITORING STARTED | @{username}",
                    file=discord.File(card)
                )

client.run(TOKEN)
