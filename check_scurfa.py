import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/" # -- in -rest out
# URL = "https://www.scurfawatches.com/product/top-side-crew-rose-gold-black-dial-mens/" #-- in -rest in
# URL = "https://www.scurfawatches.com/product/top-side-crew-stainless-steel-black-dial-mens/" # out - rest in
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


def _is_enabled(tag):
    """Return True only for purchase controls that are not disabled."""
    disabled = tag.get('disabled')
    aria_disabled = str(tag.get('aria-disabled', '')).lower()

    if disabled is not None:
        return False
    if aria_disabled == 'true':
        return False
    return True


def has_product_add_to_cart(soup):
    """Detect add-to-cart only for the current product section, not related products."""
    # WooCommerce product pages usually wrap the item in .single-product .product.
    product_root = soup.select_one('div.single-product div.product') or soup.select_one('div.product')
    if not product_root:
        return False

    # The form.cart inside product summary is the canonical buy flow for the viewed item.
    product_form = product_root.select_one('div.summary form.cart') or product_root.select_one('form.cart')
    if not product_form:
        return False

    # Require an enabled submit control that is specifically an add-to-cart action.
    add_to_cart_button = product_form.find(
        'button',
        attrs={
            'name': re.compile(r'add-to-cart', re.I),
            'class': re.compile(r'single_add_to_cart_button|add_to_cart_button', re.I),
        },
    )
    if add_to_cart_button and _is_enabled(add_to_cart_button):
        return True

    # Fallback for themes using non-standard button classes but standard form inputs.
    add_to_cart_input = product_form.find('input', attrs={'name': re.compile(r'add-to-cart', re.I)})
    submit_input = product_form.find('input', attrs={'type': re.compile(r'submit', re.I)})
    return bool(add_to_cart_input and submit_input and _is_enabled(submit_input))


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
        has_cart_form = has_product_add_to_cart(soup)

        # Some themes keep stale "awaiting stock" text in the page while still rendering
        # a live add-to-basket flow. Treat active purchase controls as source of truth.
        if has_cart_form:
            msg = f"🚨 *ITEM IN STOCK!* 🚨\nIt is ready! [Buy Now]({URL})"
            send_notifications(msg)
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock "
            f"(sold_out={is_sold_t}, page_buy_buttons={len(buy_buttons)}, product_cart_form={has_cart_form})."
        )

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    check_stock()
