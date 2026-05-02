import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Optional AI signal via Hugging Face Inference API (free tier available with token)
HF_TOKEN = os.environ.get('HF_TOKEN')
HF_MODEL = os.environ.get('HF_MODEL', 'facebook/bart-large-mnli')
USE_AI_AVAILABILITY = os.environ.get('USE_AI_AVAILABILITY', '1') == '1'

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

AUTO_CHECKOUT_ENABLED = os.environ.get('AUTO_CHECKOUT_ENABLED', '0') == '1'
CHECKOUT_EMAIL = os.environ.get('CHECKOUT_EMAIL')
CHECKOUT_FIRST_NAME = os.environ.get('CHECKOUT_FIRST_NAME')
CHECKOUT_LAST_NAME = os.environ.get('CHECKOUT_LAST_NAME')
CHECKOUT_PHONE = os.environ.get('CHECKOUT_PHONE')
CHECKOUT_ADDRESS_1 = os.environ.get('CHECKOUT_ADDRESS_1')
CHECKOUT_ADDRESS_2 = os.environ.get('CHECKOUT_ADDRESS_2', '')
CHECKOUT_CITY = os.environ.get('CHECKOUT_CITY')
CHECKOUT_STATE = os.environ.get('CHECKOUT_STATE')
CHECKOUT_POSTCODE = os.environ.get('CHECKOUT_POSTCODE')
CHECKOUT_COUNTRY = os.environ.get('CHECKOUT_COUNTRY', 'US')
CHECKOUT_CC_NUMBER = os.environ.get('CHECKOUT_CC_NUMBER')
CHECKOUT_CC_EXP_MONTH = os.environ.get('CHECKOUT_CC_EXP_MONTH')
CHECKOUT_CC_EXP_YEAR = os.environ.get('CHECKOUT_CC_EXP_YEAR')
CHECKOUT_CC_CVC = os.environ.get('CHECKOUT_CC_CVC')


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


def _checkout_config_is_complete():
    required = [
        CHECKOUT_EMAIL,
        CHECKOUT_FIRST_NAME,
        CHECKOUT_LAST_NAME,
        CHECKOUT_PHONE,
        CHECKOUT_ADDRESS_1,
        CHECKOUT_CITY,
        CHECKOUT_STATE,
        CHECKOUT_POSTCODE,
        CHECKOUT_CC_NUMBER,
        CHECKOUT_CC_EXP_MONTH,
        CHECKOUT_CC_EXP_YEAR,
        CHECKOUT_CC_CVC,
    ]
    return all(bool(v) for v in required)


def attempt_guest_checkout():
    if not AUTO_CHECKOUT_ENABLED:
        print("Auto checkout skipped: AUTO_CHECKOUT_ENABLED is false.")
        return

    if not _checkout_config_is_complete():
        print("Auto checkout skipped: missing one or more checkout secrets.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(URL, wait_until='domcontentloaded', timeout=45_000)
            page.get_by_role('button', name=re.compile(r'add to cart', re.I)).click(timeout=15_000)
            page.goto("https://www.scurfawatches.com/checkout/", wait_until='domcontentloaded', timeout=45_000)

            page.fill('#billing_email', CHECKOUT_EMAIL)
            page.fill('#billing_first_name', CHECKOUT_FIRST_NAME)
            page.fill('#billing_last_name', CHECKOUT_LAST_NAME)
            page.fill('#billing_phone', CHECKOUT_PHONE)
            page.fill('#billing_address_1', CHECKOUT_ADDRESS_1)
            if CHECKOUT_ADDRESS_2:
                page.fill('#billing_address_2', CHECKOUT_ADDRESS_2)
            page.fill('#billing_city', CHECKOUT_CITY)
            page.fill('#billing_state', CHECKOUT_STATE)
            page.fill('#billing_postcode', CHECKOUT_POSTCODE)
            page.select_option('#billing_country', CHECKOUT_COUNTRY)

            cc_input = page.locator('input[name*="cardnumber"], iframe[name*="card"]')
            if cc_input.count() == 0:
                raise RuntimeError("Card input was not found on checkout page.")

            card_number_frame = page.frame_locator('iframe[name*="card-number"], iframe[title*="number"]')
            card_exp_frame = page.frame_locator('iframe[name*="card-expiry"], iframe[title*="expiration"]')
            card_cvc_frame = page.frame_locator('iframe[name*="card-cvc"], iframe[title*="security"]')

            card_number_frame.locator('input[name="cardnumber"], input[placeholder*="Card number"]').first.fill(CHECKOUT_CC_NUMBER)
            card_exp_frame.locator('input[name="exp-date"], input[placeholder*="MM / YY"]').first.fill(
                f"{CHECKOUT_CC_EXP_MONTH}/{CHECKOUT_CC_EXP_YEAR}"
            )
            card_cvc_frame.locator('input[name="cvc"], input[placeholder*="CVC"]').first.fill(CHECKOUT_CC_CVC)

            place_order_btn = page.get_by_role('button', name=re.compile(r'place order', re.I))
            place_order_btn.click(timeout=15_000)
            print("Auto checkout attempted (guest order submitted).")
        except (PlaywrightTimeoutError, Exception) as e:
            print(f"Auto checkout failed: {e}")
        finally:
            browser.close()


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
            attempt_guest_checkout()
            return

        print(
            f"[{time.strftime('%H:%M:%S')}] Still awaiting stock "
            f"(schema_stock={schema_stock}, product_cart_form={has_cart_form}, sold_out_main={sold_out_main}, ai_vote={ai_vote})."
        )

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    check_stock()
