import argparse
import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
NTFY_TOPIC = "scurfa_yellow_titan_2026"

# Get these from your GitHub Secrets (see Step 3)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Placeholders for checkout profile (replace with real values in env vars)
CHECKOUT_PROFILE = {
    "first_name": os.environ.get("CHECKOUT_FIRST_NAME", "FIRST_NAME"),
    "last_name": os.environ.get("CHECKOUT_LAST_NAME", "LAST_NAME"),
    "age": os.environ.get("CHECKOUT_AGE", "30"),
    "email": os.environ.get("CHECKOUT_EMAIL", "you@example.com"),
    "phone": os.environ.get("CHECKOUT_PHONE", "0000000000"),
    "shipping_address_1": os.environ.get("SHIPPING_ADDRESS_1", "123 Shipping St"),
    "shipping_address_2": os.environ.get("SHIPPING_ADDRESS_2", "Apt 1"),
    "shipping_city": os.environ.get("SHIPPING_CITY", "Shipping City"),
    "shipping_state": os.environ.get("SHIPPING_STATE", "CA"),
    "shipping_zip": os.environ.get("SHIPPING_ZIP", "90001"),
    "shipping_country": os.environ.get("SHIPPING_COUNTRY", "US"),
    "billing_address_1": os.environ.get("BILLING_ADDRESS_1", "123 Billing St"),
    "billing_address_2": os.environ.get("BILLING_ADDRESS_2", "Unit 1"),
    "billing_city": os.environ.get("BILLING_CITY", "Billing City"),
    "billing_state": os.environ.get("BILLING_STATE", "CA"),
    "billing_zip": os.environ.get("BILLING_ZIP", "90001"),
    "billing_country": os.environ.get("BILLING_COUNTRY", "US"),
    "card_name": os.environ.get("CARD_NAME", "CARDHOLDER NAME"),
    "card_number": os.environ.get("CARD_NUMBER", "4111111111111111"),
    "card_exp_month": os.environ.get("CARD_EXP_MONTH", "12"),
    "card_exp_year": os.environ.get("CARD_EXP_YEAR", "2030"),
    "card_cvv": os.environ.get("CARD_CVV", "123"),
}


def send_notifications(message):
    # 1. Primary: ntfy.sh
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "SCURFA ALERT", "Priority": "urgent", "Tags": "watch"},
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
    if tag.name not in ["button", "a", "input"]:
        return False

    pattern = re.compile(r"add.*to.*(cart|basket)|buy.*now|purchase|check.*out|atc", re.I)

    if pattern.search(tag.get_text(strip=True)):
        return True

    for attr in ["class", "id", "name", "value"]:
        val = tag.get(attr, "")
        if isinstance(val, list):
            val = " ".join(val)
        if pattern.search(str(val)):
            return True

    return False


def is_sold_out(soup):
    sold_out_phrases = [r"out of stock", r"sold out", r"awaiting stock", r"unavailable", r"backorder", r"not in stock"]
    pattern = re.compile("|".join(sold_out_phrases), re.I)
    found = soup.find(string=pattern)
    return found is not None


def fill_if_present(page, selectors, value):
    for sel in selectors:
        locator = page.locator(sel)
        if locator.count() > 0 and locator.first.is_visible():
            locator.first.fill(value)
            return True
    return False


def auto_buy_with_playwright():
    """Attempts full add-to-cart and checkout flow using broad WooCommerce selectors."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    print("AUTO_BUY enabled. Launching Playwright checkout flow.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            page.get_by_role("button", name=re.compile(r"add to cart|buy now", re.I)).first.click(timeout=10000)

            # Go to cart / checkout
            try:
                page.goto("https://www.scurfawatches.com/checkout/", wait_until="domcontentloaded", timeout=45000)
            except PlaywrightTimeoutError:
                page.goto("https://www.scurfawatches.com/cart/", wait_until="domcontentloaded", timeout=45000)
                page.get_by_role("link", name=re.compile(r"proceed to checkout|checkout", re.I)).first.click(timeout=10000)

            # Billing + contact
            fill_if_present(page, ["#billing_first_name", "input[name='billing_first_name']"], CHECKOUT_PROFILE["first_name"])
            fill_if_present(page, ["#billing_last_name", "input[name='billing_last_name']"], CHECKOUT_PROFILE["last_name"])
            fill_if_present(page, ["#billing_email", "input[name='billing_email']"], CHECKOUT_PROFILE["email"])
            fill_if_present(page, ["#billing_phone", "input[name='billing_phone']"], CHECKOUT_PROFILE["phone"])
            fill_if_present(page, ["#billing_address_1", "input[name='billing_address_1']"], CHECKOUT_PROFILE["billing_address_1"])
            fill_if_present(page, ["#billing_address_2", "input[name='billing_address_2']"], CHECKOUT_PROFILE["billing_address_2"])
            fill_if_present(page, ["#billing_city", "input[name='billing_city']"], CHECKOUT_PROFILE["billing_city"])
            fill_if_present(page, ["#billing_state", "input[name='billing_state']"], CHECKOUT_PROFILE["billing_state"])
            fill_if_present(page, ["#billing_postcode", "input[name='billing_postcode']"], CHECKOUT_PROFILE["billing_zip"])

            # Optional age field when present
            fill_if_present(page, ["#age", "input[name='age']", "input[name*='age']"], CHECKOUT_PROFILE["age"])

            # Shipping (if separate address form is present)
            fill_if_present(page, ["#shipping_first_name", "input[name='shipping_first_name']"], CHECKOUT_PROFILE["first_name"])
            fill_if_present(page, ["#shipping_last_name", "input[name='shipping_last_name']"], CHECKOUT_PROFILE["last_name"])
            fill_if_present(page, ["#shipping_address_1", "input[name='shipping_address_1']"], CHECKOUT_PROFILE["shipping_address_1"])
            fill_if_present(page, ["#shipping_address_2", "input[name='shipping_address_2']"], CHECKOUT_PROFILE["shipping_address_2"])
            fill_if_present(page, ["#shipping_city", "input[name='shipping_city']"], CHECKOUT_PROFILE["shipping_city"])
            fill_if_present(page, ["#shipping_state", "input[name='shipping_state']"], CHECKOUT_PROFILE["shipping_state"])
            fill_if_present(page, ["#shipping_postcode", "input[name='shipping_postcode']"], CHECKOUT_PROFILE["shipping_zip"])

            # Card fields (works only when processor exposes standard iframes/inputs)
            fill_if_present(page, ["input[name='cardnumber']", "#wc-stripe-card-number"], CHECKOUT_PROFILE["card_number"])
            fill_if_present(page, ["input[name='exp-date']", "#wc-stripe-exp"], f"{CHECKOUT_PROFILE['card_exp_month']}/{CHECKOUT_PROFILE['card_exp_year'][-2:]}")
            fill_if_present(page, ["input[name='cvc']", "#wc-stripe-cvc"], CHECKOUT_PROFILE["card_cvv"])

            page.wait_for_timeout(1000)

            # Safety: do NOT submit by default unless explicitly enabled
            if os.environ.get("PLACE_ORDER", "false").lower() == "true":
                page.get_by_role("button", name=re.compile(r"place order|complete order|pay now", re.I)).first.click(timeout=10000)
                print("Order submission attempted.")
            else:
                print("Checkout fields filled. Set PLACE_ORDER=true to submit order.")

        finally:
            browser.close()


def check_stock(auto_buy=False):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    time.sleep(random.randint(5, 30))

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        is_sold_t = is_sold_out(soup)
        buy_button = soup.find_all(is_cart_button)

        if not is_sold_t and buy_button:
            msg = f"🚨 *ITEM IN STOCK!* 🚨\nIt is ready! [Buy Now]({URL})"
            send_notifications(msg)
            if auto_buy:
                auto_buy_with_playwright()
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Still awaiting stock.")

    except Exception as e:
        print(f"Check failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check stock and optionally run Playwright autobuy flow.")
    parser.add_argument("--autobuy", action="store_true", default=False, help="Enable Playwright autobuy flow (default: disabled).")
    args = parser.parse_args()

    check_stock(auto_buy=args.autobuy)
