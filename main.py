import threading
import time
from multiprocessing import Value

import requests

from telegramBot import runTelegramBot

online_users_count = 0
count_lock = threading.Lock()
DELAY_API_CALL = 60


def get_online_users():
    url = "https://maplelegends.com/api/get_online_users"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        online_users = response.json()  # Parse the JSON response
        return online_users
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")


def update_online_users(shared_count, count_lock):
    while True:
        online_users_data = get_online_users()
        if online_users_data:
            count = online_users_data.get("usercount", 0)
            with count_lock:
                shared_count.value = count
        time.sleep(DELAY_API_CALL)  # Update every DELAY_API_CALL seconds


if __name__ == "__main__":
    shared_count = Value("i", 0)
    count_lock = threading.Lock()

    # Start the monitoring thread
    threading.Thread(
        target=update_online_users, args=(shared_count, count_lock), daemon=True
    ).start()

    # Run the Telegram bot
    runTelegramBot(shared_count, count_lock)
