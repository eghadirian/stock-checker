import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
TARGETS = [
    {
        "name": "Titanium Yellow",
        "url": "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/",
        "sold_out_pattern": "Awaiting Stock",
        "buy_button_class_pattern": "single_add_to_cart_button",
    },
]

# Get these from your GitHub Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_notifications(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            }
            requests.post(tg_url, json=payload, timeout=10)
            print("Telegram sent.")
        except Exception as e:
            print(f"Telegram failed: {e}")
    else:
        print("Telegram is not configured; set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.")


def check_target(target):
    url = target.get("url", "")
    sold_out_pattern = target.get("sold_out_pattern", "")
    buy_button_class_pattern = target.get("buy_button_class_pattern", "")
    name = target.get("name") or url

    if not url or not sold_out_pattern or not buy_button_class_pattern:
        print(f"Skipping invalid target config: {target}")
        return

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"[{time.strftime('%H:%M:%S')}] {name}: HTTP {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        is_sold_out = soup.find(string=re.compile(sold_out_pattern, re.IGNORECASE))
        buy_button = soup.find(
            "button",
            class_=re.compile(buy_button_class_pattern, re.IGNORECASE),
        )

        if not is_sold_out and buy_button:
            msg = f"🚨 *IN STOCK!* 🚨\n{name} is available: {url}"
            send_notifications(msg)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] {name}: still sold out.")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] {name}: check failed: {e}")


def check_all_targets():
    for idx, target in enumerate(TARGETS):
        check_target(target)
        if idx < len(TARGETS) - 1:
            time.sleep(random.randint(5, 30))


if __name__ == "__main__":
    check_all_targets()
