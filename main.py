import time
import requests
import logging
import json
import os
import re
import sys
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, RetryAfter
import asyncio
import pycountry
import phonenumbers

# === CONFIG ===
BOT_TOKEN = "7610187834:AAHGjQSTaqByRiTYE94ba9pZPUtKkfz14FU"
CHAT_ID = "-1002818830065"
USERNAME = "akash660"
PASSWORD = "RuhiRobiul098@#"
BASE_URL = "http://94.23.120.156"
LOGIN_PAGE_URL = BASE_URL + "/ints/login"
LOGIN_POST_URL = BASE_URL + "/ints/signin"
DATA_URL = BASE_URL + "/ints/agent/res/data_smscdr.php"

bot = Bot(token=BOT_TOKEN)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

logging.basicConfig(level=logging.INFO, format='\033[92m[%(asctime)s] [%(levelname)s] %(message)s\033[0m', datefmt='%Y-%m-%d %H:%M:%S')

def escape_markdown(text: str) -> str:
    return re.sub(r'([_*()~`>#+=|{}.!-])', r'\\\1', text)

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

logging.info('Script By @Robiul_TNE_R')

def login():
    try:
        resp = session.get(LOGIN_PAGE_URL)
        match = re.search(r'What is (\d+) \+ (\d+)', resp.text)
        if not match:
            logging.error("Captcha not found.")
            return False
        num1, num2 = int(match.group(1)), int(match.group(2))
        captcha_answer = num1 + num2
        logging.info(f"Solved captcha: {num1} + {num2} = {captcha_answer}")
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "capt": captcha_answer
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": LOGIN_PAGE_URL
        }
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
    return (
        f"{DATA_URL}?fdate1={start_date}%2000:00:00&fdate2={end_date}%2023:59:59&"
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
        "sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1"
    )

if not (CHAT_ID.startswith('-1') and CHAT_ID.endswith('65')):
    sys.exit(1)

def fetch_data():
    url = build_api_url()
    headers = {"X-Requested-With": "XMLHttpRequest"}
    try:
        response = session.get(url, headers=headers, timeout=10)
        logging.info(f"Response Status: {response.status_code}")
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logging.error(f"[!] JSON decode error: {e}")
                logging.debug("Partial response:\n" + response.text[:300])
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

def get_country_by_number(number):
    try:
        parsed_number = phonenumbers.parse("+" + number, None)
        country_code = phonenumbers.region_code_for_number(parsed_number)
        if country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                country_name = country.name
                flag = ''.join([chr(127397 + ord(c)) for c in country_code])
                return country_name, flag
        return 'Unknown', '🌐'
    except:
        return 'Unknown', '🌐'

async def sent_messages():
    logging.info("🔍 Checking for messages...\n")
    data = fetch_data()
    if data and 'aaData' in data:
        for row in data['aaData']:
            date = str(row[0]).strip()
            number = str(row[2]).strip()
            full_range = str(row[1]).strip()
            service = str(row[3]).strip()
            message = str(row[5]).strip()

            # ✅ Replace FACEBOOK with WHATSAPP if present
            if "FACEBOOK" in message:
                message = message.replace("FACEBOOK", "WHATSAPP")

            if "FACEBOOK" in service:
                service = service.replace("FACEBOOK", "WHATSAPP")

            match = re.search(r'(\d{3}-\d{3}|\d{4,8})', message)
            otp = match.group() if match else None

            if otp:
                unique_key = f"{number}|{otp}"
                if unique_key not in already_sent:
                    already_sent.add(unique_key)

                    country_name, flag = get_country_by_number(number)
                    text = (
                        "✨ " + flag + " " + country_name + " *" + service + " OTP ALERT‼️*\n"
                        "🕰️ *Time:* `" + date + "`\n"
                        "📞 *Number:* `" + mask_number(number) + "`\n"
                        "🌍 *Country:* " + country_name + " " + flag + "\n"
                        "🔑 *Your Main OTP:* `" + otp + "`\n"
                        "🍏 *Service:* `" + service + "`\n"
                        "📬 *Full Message:*\n"
                        "```text\n" + message.strip() + "\n```\n"
                        "👑 *Powered by:* [Robiul_TNE_R]"
                    )

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🏆Main Channel", url="https://t.me/TRICK_EARN_R"),
                            InlineKeyboardButton("♻️Backup Channel", url="https://t.me/World_of_Method")
                        ],
                        [
                            InlineKeyboardButton("📚All Number", url="https://t.me/+Grzx-jay05BmOTI9")
                        ]
                    ])

                    try:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=text,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        save_already_sent(already_sent)
                        logging.info(f"[+] Sent OTP: {otp}")
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

async def main():
    if login():
        while True:
            await sent_messages()
            await asyncio.sleep(3)
    else:
        logging.error("Initial login failed. Exiting...")

asyncio.run(main())
