import requests
from bs4 import BeautifulSoup
import time
import random
import re
import os

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Get these from your GitHub Secrets (see Step 3)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_notifications(message):
    # 1. Primary: ntfy.sh
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": "SCURFA ALERT", "Priority": "urgent", "Tags": "watch"})
        print("ntfy sent.")
    except Exception as e:
        print(f"ntfy failed: {e}")

    # 2. Backup: Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(tg_url, json=payload, timeout=10)
            print("Telegram sent.")
        except Exception as e:
            print(f"Telegram failed: {e}")

def check_stock():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    time.sleep(random.randint(5, 30))

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        if response.status_code != 200: return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Stricter detection logic
        is_sold_out = soup.find(string=re.compile(r'Awaiting Stock', re.IGNORECASE))
        buy_button = soup.find("button", class_=re.compile(r'single_add_to_cart_button', re.IGNORECASE))
        
        if not is_sold_out and buy_button:
            msg = f"🚨 *SCURFA IN STOCK!* 🚨\nThe Titanium Yellow is ready! [Buy Now]({URL})"
            send_notifications(msg)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Still awaiting stock.")
            
    except Exception as e:
        print(f"Check failed: {e}")

if __name__ == "__main__":
    check_stock()
