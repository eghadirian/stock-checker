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


def _is_enabled(tag):
    """Return True only for purchase controls that are not disabled."""
    disabled = tag.get('disabled')
    aria_disabled = str(tag.get('aria-disabled', '')).lower()

    if disabled is not None:
        return False
    if aria_disabled == 'true':
        return False
    return True


def _extract_main_product_name(soup):
    """Try to identify the exact product name for this URL page."""
    # Best source on WooCommerce product pages.
    heading = soup.select_one('div.single-product div.product h1.product_title, h1.product_title')
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)

    # Fallbacks.
    og_title = soup.find('meta', attrs={'property': 'og:title'})
    if og_title and og_title.get('content'):
        return og_title.get('content').strip()

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)

    return None


def has_main_product_add_to_cart(soup):
    """Detect add-to-cart only for the current product section, not related products/ads."""
    product_root = soup.select_one('div.single-product div.product') or soup.select_one('div.product')
    if not product_root:
        return False

    # Main item flow is in summary/cart under the root product.
    product_form = product_root.select_one('div.summary form.cart') or product_root.select_one('form.cart')
    if not product_form:
        return False

    add_to_cart_button = product_form.find(
        'button',
        attrs={
            'name': re.compile(r'add-to-cart', re.I),
            'class': re.compile(r'single_add_to_cart_button|add_to_cart_button', re.I),
        },
    )
    if add_to_cart_button and _is_enabled(add_to_cart_button):
        return True

    # Some themes use submit input with add-to-cart hidden input.
    add_to_cart_input = product_form.find('input', attrs={'name': re.compile(r'add-to-cart', re.I)})
    submit_input = product_form.find('input', attrs={'type': re.compile(r'submit', re.I)})
    return bool(add_to_cart_input and submit_input and _is_enabled(submit_input))


def has_main_product_schema_in_stock(soup):
    """Use structured Product schema as a strong signal for exact product availability."""
    main_name = _extract_main_product_name(soup)
    scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

    for script in scripts:
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        text = raw.lower()
        if '"@type"' not in text or 'product' not in text:
            continue

        # Scope to the main product only when possible.
        if main_name and main_name.lower() not in text:
            continue

        if 'instock' in text:
            return True

        if 'outofstock' in text:
            return False

    return None


def is_sold_out_in_main_product(soup):
    """Look for sold-out copy only in the main product container."""
    product_root = soup.select_one('div.single-product div.product') or soup.select_one('div.product')
    if not product_root:
        return False

    sold_out_phrases = [
        r'out of stock',
        r'sold out',
        r'awaiting stock',
        r'unavailable',
        r'backorder',
        r'not in stock',
    ]
    pattern = re.compile('|'.join(sold_out_phrases), re.I)
    found = product_root.find(string=pattern)
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

        schema_stock = has_main_product_schema_in_stock(soup)
        has_cart_form = has_main_product_add_to_cart(soup)
        sold_out_main = is_sold_out_in_main_product(soup)

        # Decision order: exact product schema -> exact product add-to-cart flow -> sold-out signal.
        in_stock = (schema_stock is True) or has_cart_form
        if in_stock and not sold_out_main:
            msg = f"🚨 *ITEM IN STOCK!* 🚨\nIt is ready! [Buy Now]({URL})"
            send_notifications(msg)
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock "
            f"(schema_stock={schema_stock}, product_cart_form={has_cart_form}, sold_out_main={sold_out_main})."
        )

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    check_stock()
