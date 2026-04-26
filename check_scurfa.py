import requests
from bs4 import BeautifulSoup
import os
import time
import random

# --- CONFIGURATION ---
URL = "https://www.scurfawatches.com/product/diver-one-d1-500-titanium-yellow-2025/"
# This must match exactly what you typed in the phone app
NTFY_TOPIC = "scurfa_yellow_titan_2026" 

def send_notification(message):
    try:
        # ntfy.sh is a simple POST request. No API key needed!
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": "SCURFA WATCH ALERT",
                "Priority": "urgent",
                "Tags": "watch,rotating_light"
            })
        print("Notification pushed to phone!")
    except Exception as e:
        print(f"Error sending notification: {e}")

def check_stock():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Stealth delay: GitHub starts the job, but we wait 1-30s before hitting Scurfa
    time.sleep(random.randint(1, 30))

    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # We look for the "Add to basket" button. 
        # If it's there, or if "Awaiting Stock" is gone, we alert.
        if "add to basket" in soup.get_text().lower() or "awaiting stock" not in soup.get_text().lower():
            print("WATCH FOUND!")
            send_notification(f"The Titanium Yellow is IN STOCK! Buy now: {URL}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Still checking...")
            
    except Exception as e:
        print(f"Site check failed: {e}")

if __name__ == "__main__":
    check_stock()
