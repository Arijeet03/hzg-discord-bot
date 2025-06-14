import random
import requests
from bs4 import BeautifulSoup
import discord
import json
import asyncio
from urllib.parse import urljoin

# Load config
with open('config.json') as f:
    config = json.load(f)

LOGIN_URL = "https://forums.hzgaming.net/login.php?do=login"
FORUM_URL = config["forum_url"]
USERNAME = config["username"]
PASSWORD = config["password"]
CHANNEL_ID = int(config["channel_id"])
CHECK_MIN = 30
CHECK_MAX = 240


intents = discord.Intents.default()
client = discord.Client(intents=intents)

session = requests.Session()
seen_threads = set()

def login_to_forum():
    resp = session.get(LOGIN_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    token_input = soup.find("input", {"name": "securitytoken"})
    token = token_input["value"] if token_input else "guest"

    payload = {
        'vb_login_username': USERNAME,
        'vb_login_password': PASSWORD,
        'vb_login_md5password': '',
        'vb_login_md5password_utf': '',
        'cookieuser': '1',
        'securitytoken': token,
        'do': 'login'
    }

    login_resp = session.post(LOGIN_URL, data=payload)
    if "You have entered an invalid username or password" in login_resp.text:
        raise Exception("Login failed. Check credentials.")
    print("[+] Logged in to forum.")

def get_pending_threads():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    response = session.get(FORUM_URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    if "You must log in" in response.text or soup.find("input", {"name": "vb_login_username"}):
        print("[!] Session expired. Re-logging in.")
        login_to_forum()
        response = session.get(FORUM_URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

    thread_blocks = soup.find_all("div", class_="rating0 nonsticky")
    found = []

    for block in thread_blocks:
        prefix_span = block.find("span", style=lambda val: val and "font-weight: bold" in val)
        if prefix_span and "[PENDING ADMIN]" in prefix_span.text:
            title_tag = block.find("a", class_="title")
            if title_tag:
                title = title_tag.text.strip()
                relative_link = title_tag.get("href")
                full_url = urljoin("https://forums.hzgaming.net/", relative_link)
                found.append((title, full_url))

    return found

@client.event
async def on_ready():
    print(f"[+] Logged into Discord as {client.user}")
    login_to_forum()
    await monitor_forum()

async def monitor_forum():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print(f"[!] Could not find channel with ID {CHANNEL_ID}")
        return

    while True:
        pending_threads = get_pending_threads()
        new_threads = [t for t in pending_threads if t[1] not in seen_threads]

        for title, link in new_threads:
            seen_threads.add(link)
            ping = f"<@{config['ping_user_id']}>"
            await channel.send(f"{ping} 🆕 New thread posted:\n**{title}**\n{link}")
            print(f"[+] Notified Discord: {title}")

        if not new_threads:
            print("[*] No new PENDING ADMIN threads found.")

        sleep_time = random.randint(CHECK_MIN, CHECK_MAX)
        print(f"[*] Sleeping for {sleep_time} seconds...")
        await asyncio.sleep(sleep_time)


client.run(config["discord_token"])
