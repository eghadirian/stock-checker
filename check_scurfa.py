import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
URL = "https://www.scurfawatches.com/product/top-side-crew-rose-gold-black-dial-mens/"
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Get these from your GitHub Secrets (see Step 3)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


def send_notifications(message):
    # 1. Primary: ntfy.sh
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": "SCURFA ALERT", "Priority": "urgent", "Tags": "watch"},
            timeout=10,
        )
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


def is_cart_button(tag):
    # Target common clickable elements
    if tag.name not in ['button', 'a', 'input']:
        return False

    # A generic regex pattern for common shopping actions.
    # Includes variants often used by WooCommerce themes.
    pattern = re.compile(
        r'add.*to.*(cart|basket)|buy.*now|purchase|check.*out|atc|add_to_cart|single_add_to_cart_button',
        re.I,
    )

    # 1. Check visible text (e.g., <button>Add to Cart</button>)
    if pattern.search(tag.get_text(strip=True)):
        return True

    # 2. Check internal attributes (class, id, name, value)
    for attr in ['class', 'id', 'name', 'value', 'href', 'data-product_id']:
        val = tag.get(attr, "")
        if isinstance(val, list):
            val = " ".join(val)
        if pattern.search(str(val)):
            return True

    return False


def has_add_to_cart_form(soup):
    """Detect an active add-to-cart form used by many e-commerce templates."""
    form = soup.find('form', attrs={'class': re.compile(r'cart', re.I)})
    if not form:
        return False

    return form.find('button', attrs={'name': re.compile(r'add-to-cart', re.I)}) is not None


def is_sold_out(soup):
    # List of common phrases used when an item is unavailable
    sold_out_phrases = [
        r'out of stock',
        r'sold out',
        r'awaiting stock',
        r'unavailable',
        r'backorder',
        r'not in stock',
    ]
    pattern = re.compile('|'.join(sold_out_phrases), re.I)
    found = soup.find(string=pattern)
    return found is not None


def check_stock():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    time.sleep(random.randint(5, 30))

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        is_sold_t = is_sold_out(soup)
        buy_buttons = soup.find_all(is_cart_button)
        has_cart_form = has_add_to_cart_form(soup)

        # Some themes keep stale "awaiting stock" text in the page while still rendering
        # a live add-to-basket flow. Treat active purchase controls as source of truth.
        if buy_buttons or has_cart_form:
            msg = f"🚨 *ITEM IN STOCK!* 🚨\nIt is ready! [Buy Now]({URL})"
            send_notifications(msg)
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock "
            f"(sold_out={is_sold_t}, buy_buttons={len(buy_buttons)}, cart_form={has_cart_form})."
        )

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    check_stock()
