import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Optional AI signal via Hugging Face Inference API (free tier available with token)
HF_TOKEN = os.environ.get('HF_TOKEN')
HF_MODEL = os.environ.get('HF_MODEL', 'facebook/bart-large-mnli')
USE_AI_AVAILABILITY = os.environ.get('USE_AI_AVAILABILITY', '1') == '1'

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


def send_notifications(message):
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

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(tg_url, json=payload, timeout=10)
            print("Telegram sent.")
        except Exception as e:
            print(f"Telegram failed: {e}")


def _is_enabled(tag):
    disabled = tag.get('disabled')
    aria_disabled = str(tag.get('aria-disabled', '')).lower()
    return disabled is None and aria_disabled != 'true'


def _extract_main_product_name(soup):
    heading = soup.select_one('div.single-product div.product h1.product_title, h1.product_title')
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)

    og_title = soup.find('meta', attrs={'property': 'og:title'})
    if og_title and og_title.get('content'):
        return og_title.get('content').strip()

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return None


def _main_product_root(soup):
    return soup.select_one('div.single-product div.product') or soup.select_one('div.product')


def has_main_product_add_to_cart(soup):
    product_root = _main_product_root(soup)
    if not product_root:
        return False

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

    add_to_cart_input = product_form.find('input', attrs={'name': re.compile(r'add-to-cart', re.I)})
    submit_input = product_form.find('input', attrs={'type': re.compile(r'submit', re.I)})
    return bool(add_to_cart_input and submit_input and _is_enabled(submit_input))


def has_main_product_schema_in_stock(soup):
    main_name = _extract_main_product_name(soup)
    scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

    for script in scripts:
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        text = raw.lower()
        if '"@type"' not in text or 'product' not in text:
            continue
        if main_name and main_name.lower() not in text:
            continue

        if 'instock' in text:
            return True
        if 'outofstock' in text:
            return False

    return None


def is_sold_out_in_main_product(soup):
    product_root = _main_product_root(soup)
    if not product_root:
        return False

    sold_out_phrases = [r'out of stock', r'sold out', r'awaiting stock', r'unavailable', r'backorder', r'not in stock']
    pattern = re.compile('|'.join(sold_out_phrases), re.I)
    return product_root.find(string=pattern) is not None


def _main_product_text_for_ai(soup, max_chars=2500):
    product_root = _main_product_root(soup)
    if not product_root:
        return ''

    # Keep content limited to avoid sending unrelated sections to AI.
    text = ' '.join(product_root.stripped_strings)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


def ai_availability_vote(soup):
    """Optional AI vote: returns True (in stock), False (out), or None (unknown/disabled)."""
    if not USE_AI_AVAILABILITY or not HF_TOKEN:
        return None

    context = _main_product_text_for_ai(soup)
    if not context:
        return None

    labels = ["in stock", "out of stock", "unknown"]
    payload = {
        "inputs": context,
        "parameters": {
            "candidate_labels": labels,
            "multi_label": False,
            "hypothesis_template": "This product is {}.",
        },
    }

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

    try:
        result = requests.post(url, headers=headers, json=payload, timeout=20)
        if result.status_code != 200:
            print(f"AI availability skipped (status={result.status_code}).")
            return None

        data = result.json()
        returned_labels = [label.lower() for label in data.get('labels', [])]
        returned_scores = data.get('scores', [])
        if not returned_labels or not returned_scores:
            return None

        top = returned_labels[0]
        top_score = float(returned_scores[0])
        if top_score < 0.60:
            return None
        if top == 'in stock':
            return True
        if top == 'out of stock':
            return False
        return None
    except Exception as e:
        print(f"AI availability skipped ({e}).")
        return None


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
        ai_vote = ai_availability_vote(soup)

        # Deterministic signals first; AI only complements when deterministic checks conflict/miss.
        in_stock = (schema_stock is True) or has_cart_form or (ai_vote is True and not sold_out_main)
        if in_stock and not sold_out_main:
            msg = f"🚨 *ITEM IN STOCK!* 🚨\nIt is ready! [Buy Now]({URL})"
            send_notifications(msg)
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock "
            f"(schema_stock={schema_stock}, product_cart_form={has_cart_form}, sold_out_main={sold_out_main}, ai_vote={ai_vote})."
        )

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    check_stock()
