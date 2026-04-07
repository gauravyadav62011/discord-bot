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
    print("ERROR: TOKEN NOT FOUND")
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

# ================= HELPERS =================
def extract_username(text):
    match = re.search(r"(?:instagram\.com/)?@?([a-zA-Z0-9._]+)", text)
    return match.group(1) if match else None

def get_instagram_data(username):
    try:
        url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            return None

        data = r.json()
        user = data["graphql"]["user"]

        return {
            "username": user["username"],
            "followers": user["edge_followed_by"]["count"],
            "profile_pic": user["profile_pic_url_hd"]
        }
    except:
        return None

# ================= TILE UI =================
def create_card(username, followers, status):
    width, height = 800, 250
    img = Image.new("RGB", (width, height), (15, 15, 25))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("Poppins-Bold.ttf", 42)
        text_font = ImageFont.truetype("Poppins-Regular.ttf", 26)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # Username
    draw.text((180, 50), username, font=title_font, fill=(255, 255, 255))

    # Followers
    draw.text((180, 110), f"{followers} followers", font=text_font, fill=(180, 180, 180))

    # Status
    status_color = (0, 200, 255) if status == "ACTIVE" else (255, 180, 0)
    draw.rectangle((180, 150, 340, 190), fill=status_color)
    draw.text((190, 155), status, font=text_font, fill=(0, 0, 0))

    # Avatar placeholder
    draw.ellipse((30, 50, 130, 150), fill=(60, 60, 80))

    return img

async def send_card(channel, username, followers, status):
    card = create_card(username, followers, status)

    buffer = BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(buffer, filename="card.png")
    await channel.send(file=file)

# ================= MONITOR =================
async def monitor_accounts():
    await client.wait_until_ready()

    while not client.is_closed():
        for username in list(tracked_accounts.keys()):
            data = get_instagram_data(username)

            if data:
                tracked_accounts[username]["status"] = "active"
                tracked_accounts[username]["followers"] = data["followers"]
                tracked_accounts[username]["last_checked"] = str(datetime.now())
            else:
                tracked_accounts[username]["status"] = "monitoring"

        save_data(tracked_accounts)
        await asyncio.sleep(60)

# ================= CLIENT =================
class MyClient(discord.Client):
    async def setup_hook(self):
        self.loop.create_task(monitor_accounts())

client = MyClient(intents=intents)

# ================= EVENTS =================
@client.event
async def on_ready():
    print(f"Bot running as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    username = extract_username(message.content)
    if not username:
        return

    data = get_instagram_data(username)

    if not data:
        await send_card(message.channel, username, 0, "MONITORING")

        tracked_accounts[username] = {
            "status": "monitoring",
            "added_at": str(datetime.now())
        }
        save_data(tracked_accounts)
        return

    await send_card(message.channel, data["username"], data["followers"], "ACTIVE")

    tracked_accounts[username] = {
        "status": "active",
        "followers": data["followers"],
        "last_checked": str(datetime.now())
    }
    save_data(tracked_accounts)

# ================= START =================
client.run(TOKEN)
