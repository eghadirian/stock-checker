import requests
from bs4 import BeautifulSoup
import os
import time
import random
import re

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
NTFY_TOPIC = "scurfa_yellow_titan_2026" 

def send_notification(message, priority="urgent"):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": "SCURFA WATCH ALERT",
                "Priority": priority,
                "Tags": "watch,rotating_light"
            })
    except Exception as e:
        print(f"Error sending notification: {e}")

def check_stock():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    
    # Random delay to stay under the radar
    time.sleep(random.randint(5, 40))

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        
        # FIX 1: Check if the website actually loaded correctly
        if response.status_code != 200:
            print(f"Site error: {response.status_code}. Skipping this check.")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # FIX 2: Look for the SPECIFIC "Add to basket" button class or text
        # We look for the button specifically rather than just 'any' text on the page
        buy_button = soup.find(string=re.compile(r'add to basket', re.IGNORECASE))
        cart_form = soup.find("form", class_="cart")
        
        # If the button exists OR the cart form is visible
        if buy_button or cart_form:
            print("WATCH FOUND! Sending notification...")
            send_notification(f"TITANIUM YELLOW IS LIVE! Buy now: {URL}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Still 'Awaiting Stock'. No false alarm.")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_stock()
