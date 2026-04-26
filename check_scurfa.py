import requests
from bs4 import BeautifulSoup
import time
import random
import re

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
URL = "https://www.scurfawatches.com/product/top-side-crew-rose-gold-black-dial-mens/"
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    # Random delay to stay stealthy
    time.sleep(random.randint(5, 30))

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        
        # FAILSAFE 1: If the site returns an error (403, 503, 404), STOP.
        if response.status_code != 200:
            print(f"Site returned error {response.status_code}. Skipping to avoid false positive.")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # FAILSAFE 2: Verify we are actually on the Yellow Titanium page
        # (Checks if the specific title is in the main heading)
        page_title = soup.find("h1")
        # if not page_title or "Titanium Yellow" not in page_title.get_text():
        #     print("Could not verify page title. Skipping.")
        #     return

        # FAILSAFE 3: Look for the specific 'Awaiting Stock' text. 
        # If this text exists, the watch is DEFINITELY NOT ready.
        is_sold_out = soup.find(string=re.compile(r'Awaiting Stock', re.IGNORECASE))
        
        # FAILSAFE 4: Look for the 'Add to basket' button.
        # Scurfa uses a specific class for their primary buy button.
        buy_button = soup.find("button", class_=re.compile(r'single_add_to_cart_button', re.IGNORECASE))
        
        # LOGIC: Only alert if "Awaiting Stock" is GONE and the "Buy Button" is PRESENT.
        if not is_sold_out and buy_button:
            print("REAL STOCK DETECTED!")
            send_notification(f"TITANIUM YELLOW IS LIVE! Buy now: {URL}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Still Awaiting Stock. No false alarm.")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_stock()
