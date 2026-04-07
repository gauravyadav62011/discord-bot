import discord
import requests
import asyncio
import os
import re
import json
from datetime import datetime

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
        await message.channel.send(f"🛰️ MONITORING STARTED | @{username}")

        tracked_accounts[username] = {
            "status": "monitoring",
            "added_at": str(datetime.now())
        }
        save_data(tracked_accounts)
        return

    embed = discord.Embed(
        title="ACCOUNT ACTIVE",
        description=f"@{data['username']}",
        color=0x00ffcc
    )

    embed.add_field(name="Followers", value=data["followers"], inline=False)
    embed.set_thumbnail(url=data["profile_pic"])

    await message.channel.send(embed=embed)

    tracked_accounts[username] = {
        "status": "active",
        "followers": data["followers"],
        "last_checked": str(datetime.now())
    }
    save_data(tracked_accounts)

# ================= START =================
client.run(TOKEN)
