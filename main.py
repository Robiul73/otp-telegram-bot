import time
import requests
import logging
import json
import os
import re
import sys
import threading
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, RetryAfter
import asyncio
import pycountry
import phonenumbers

# === CONFIG ===
BOT_TOKEN = "7610187834:AAHGjQSTaqByRiTYE94ba9pZPUtKkfz14FU"
CHAT_ID = "-1002818830065"
USERNAME = "XZRMUNNA1206"
PASSWORD = "XZRMUNNA8790"
BASE_URL = "http://94.23.120.156"
LOGIN_PAGE_URL = BASE_URL + "/ints/login"
LOGIN_POST_URL = BASE_URL + "/ints/signin"
DATA_URL = BASE_URL + "/ints/agent/res/data_smscdr.php"
OWNER_ID = 8166829424
APPROVED_CHATS_FILE = "approved_chats.txt"

bot = Bot(token=BOT_TOKEN)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

logging.basicConfig(level=logging.INFO, format='\033[92m[%(asctime)s] [%(levelname)s] %(message)s\033[0m', datefmt='%Y-%m-%d %H:%M:%S')

bot_running = False
approved_chats = set()
offset = None

# === Load & Save Approved Chats ===
def load_approved_chats():
    if not os.path.exists(APPROVED_CHATS_FILE):
        return set()
    with open(APPROVED_CHATS_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())

def save_approved_chats(chats):
    with open(APPROVED_CHATS_FILE, "w") as f:
        for chat_id in chats:
            f.write(f"{chat_id}\n")

approved_chats = load_approved_chats()

# === OTP Script Functions ===

def escape_markdown(text: str) -> str:
    return re.sub(r'([_*()~`>#+=|{}.!-])', r'\\1', text)

def mask_number(number: str) -> str:
    if len(number) > 11:
        return number[:7] + '**' + number[-2:]
    elif len(number) > 9:
        return number[:7] + '**' + number[-2:]
    elif len(number) > 7:
        return number[:7] + '**' + number[-1:]
    elif len(number) > 5:
        return number[:7] + '**'
    else:
        return number

def save_already_sent(already_sent):
    with open("already_sent.json", "w") as f:
        json.dump(list(already_sent), f)

def load_already_sent():
    if os.path.exists("already_sent.json"):
        with open("already_sent.json", "r") as f:
            return set(json.load(f))
    return set()

def login():
    try:
        resp = session.get(LOGIN_PAGE_URL)
        match = re.search(r'What is (\d+) + (\d+)', resp.text)
        if not match:
            logging.error("Captcha not found.")
            return False
        num1, num2 = int(match.group(1)), int(match.group(2))
        captcha_answer = num1 + num2
        logging.info(f"Solved captcha: {num1} + {num2} = {captcha_answer}")

        payload = {"username": USERNAME, "password": PASSWORD, "capt": captcha_answer}
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": LOGIN_PAGE_URL}

        resp = session.post(LOGIN_POST_URL, data=payload, headers=headers)

        if "dashboard" in resp.text.lower() or "logout" in resp.text.lower():
            logging.info("Login successful ✅")
            return True
        else:
            logging.error("Login failed ❌")
            return False
    except Exception as e:
        logging.error(f"Login error: {e}")
        return False

def build_api_url():
    start_date = "2025-05-05"
    end_date = "2026-01-01"
    return (f"{DATA_URL}?fdate1={start_date}%2000:00:00&fdate2={end_date}%2023:59:59&"
            "frange=&fclient=&fnum=&fcli=&fgdate=&fgmonth=&fgrange=&fgclient=&fgnumber=&fgcli=&fg=0&"
            "sEcho=1&iColumns=9&sColumns=%2C%2C%2C%2C%2C%2C%2C%2C&iDisplayStart=0&iDisplayLength=25&"
            "mDataProp_0=0&sSearch_0=&bRegex_0=false&bSearchable_0=true&bSortable_0=true&"
            "mDataProp_1=1&sSearch_1=&bRegex_1=false&bSearchable_1=true&bSortable_1=true&"
            "mDataProp_2=2&sSearch_2=&bRegex_2=false&bSearchable_2=true&bSortable_2=true&"
            "mDataProp_3=3&sSearch_3=&bRegex_3=false&bSearchable_3=true&bSortable_3=true&"
            "mDataProp_4=4&sSearch_4=&bRegex_4=false&bSearchable_4=true&bSortable_4=true&"
            "mDataProp_5=5&sSearch_5=&bRegex_5=false&bSearchable_5=true&bSortable_5=true&"
            "mDataProp_6=6&sSearch_6=&bRegex_6=false&bSearchable_6=true&bSortable_6=true&"
            "mDataProp_7=7&sSearch_7=&bRegex_7=false&bSearchable_7=true&bSortable_7=true&"
            "mDataProp_8=8&sSearch_8=&bRegex_8=false&bSearchable_8=true&bSortable_8=false&"
            "sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1")

def fetch_data():
    url = build_api_url()
    headers = {"X-Requested-With": "XMLHttpRequest"}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")
                return None
        elif response.status_code == 403 or "login" in response.text.lower():
            logging.warning("Session expired. Re-logging...")
            if login():
                return fetch_data()
            return None
        else:
            logging.error(f"Unexpected error: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        return None

already_sent = load_already_sent()

async def sent_messages():
    if not bot_running:
        return

    data = fetch_data()
    if data and 'aaData' in data:
        for row in data['aaData']:
            date = str(row[0]).strip()
            number = str(row[2]).strip()
            service = str(row[3]).strip()
            message = str(row[5]).strip()

            match = re.search(r'(\d{3}-\d{3}|\d{4,8})', message)
            otp = match.group() if match else None

            if otp:
                unique_key = f"{number}|{otp}"
                if unique_key not in already_sent:
                    already_sent.add(unique_key)
                    text = (f"✨ *{service} OTP ALERT‼️*\n"
                            f"🕰️ *Time:* `{date}`\n"
                            f"📞 *Number:* `{mask_number(number)}`\n"
                            f"🔑 *Your Main OTP:* `{otp}`\n"
                            f"🍏 *Service:* `{service}`\n"
                            f"📬 *Full Message:*\n"
                            f"```text\n{message.strip()}\n```\n"
                            f"👑 *Powered by:* [@Robiul_TNE_R]")

                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏆Main Channel", url="https://t.me/+nIVhh9hJWs4wMjBl"),
                         InlineKeyboardButton("♻️Backup Channel", url="https://t.me/World_of_Method")],
                        [InlineKeyboardButton("📚All Number", url="https://t.me/+6TYPKegN5ts0OTg1")]
                    ])

                    try:
                        for chat in [CHAT_ID] + list(approved_chats):
                            await bot.send_message(chat_id=chat, text=text, parse_mode="Markdown", reply_markup=keyboard)
                            logging.info(f"OTP Sent to {chat}: {otp}")
                        save_already_sent(already_sent)
                    except RetryAfter as e:
                        logging.warning(f"Telegram Flood Control: Sleeping for {e.retry_after} seconds.")
                        await asyncio.sleep(e.retry_after)
                    except TimedOut:
                        logging.error("Telegram TimedOut")
                    except Exception as e:
                        logging.error(f"Telegram error: {e}")
            else:
                logging.info(f"No OTP found in: {message}")
    else:
        logging.info("No data or invalid response.")

async def command_listener():
    global bot_running, approved_chats, offset

    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": offset, "timeout": 10})
            data = res.json()

            if data["ok"]:
                for result in data["result"]:
                    offset = result["update_id"] + 1
                    if "message" in result:
                        msg = result["message"]
                        text = msg.get("text", "")
                        sender_id = msg["from"]["id"]
                        chat_id = msg["chat"]["id"]

                        if not text.startswith("/"):
                            continue

                        if text.startswith("/approve") or text.startswith("/remove") or text == "/list":
                            if sender_id != OWNER_ID:
                                requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                             params={"chat_id": chat_id, "text": "🚫 আপনি এই কমান্ডটি ব্যবহার করতে পারবেন না!", "parse_mode": "Markdown"})
                                continue

                        if text == "/start":
                            bot_running = True
                            await bot.send_message(chat_id=chat_id, text="✅ Bot Started!")

                        elif text == "/stop":
                            bot_running = False
                            await bot.send_message(chat_id=chat_id, text="⛔ Bot Stopped!")

                        elif text.startswith("/approve "):
                            new_chat = text.split(" ", 1)[1].strip()
                            approved_chats.add(new_chat)
                            save_approved_chats(approved_chats)
                            await bot.send_message(chat_id=chat_id, text=f"✅ Approved chat: `{new_chat}`", parse_mode="Markdown")

                        elif text.startswith("/remove "):
                            remove_chat = text.split(" ", 1)[1].strip()
                            approved_chats.discard(remove_chat)
                            save_approved_chats(approved_chats)
                            await bot.send_message(chat_id=chat_id, text=f"❌ Removed chat: `{remove_chat}`", parse_mode="Markdown")

                        elif text == "/list":
                            chat_list = '\n'.join(approved_chats) or "❌ No approved chats."
                            await bot.send_message(chat_id=chat_id, text=f"*Approved Chats:*\n`{chat_list}`", parse_mode="Markdown")

        except Exception as e:
            logging.info(f"Error in command_listener loop: {e}")
            await asyncio.sleep(5)

async def main():
    if login():
        while True:
            await sent_messages()
            await asyncio.sleep(3)
    else:
        logging.error("Initial login failed. Exiting...")

async def run_bot():
    await asyncio.gather(command_listener(), main())

if __name__ == "__main__":
    asyncio.run(run_bot())
