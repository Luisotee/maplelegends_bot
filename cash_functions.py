import asyncio
import json
import os
from asyncio.log import logger
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ContextTypes

CASH_WATCHERS_FILE = "cash_watchers.json"
cash_watchers = {}


def load_cash_watchers():
    global cash_watchers
    if os.path.exists(CASH_WATCHERS_FILE):
        with open(CASH_WATCHERS_FILE, "r") as f:
            cash_watchers = json.load(f)
    else:
        cash_watchers = {}


async def remove_cash_watcher(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 1:
        await update.message.reply_text("Usage: /removeCashWatcher <username>")
        return

    username_to_remove = args[0]

    if user_id not in cash_watchers or not cash_watchers[user_id]:
        await update.message.reply_text("You don't have any registered cash watchers.")
        return

    for entry in cash_watchers[user_id]:
        if entry["username"].lower() == username_to_remove.lower():
            cash_watchers[user_id].remove(entry)
            save_cash_watchers()
            schedule_cash_updates(context)
            await update.message.reply_text(
                f"Successfully removed cash watcher for {entry['username']}."
            )
            return

    await update.message.reply_text(
        f"No cash watcher found for username: {username_to_remove}"
    )


def schedule_cash_updates(context: ContextTypes.DEFAULT_TYPE):
    # Remove all existing cash update jobs
    for job in context.job_queue.get_jobs_by_name("cash_update"):
        job.schedule_removal()

    # Schedule new jobs for each user and each of their watched accounts
    for user_id, accounts in cash_watchers.items():
        for account in accounts:
            update_time = datetime.strptime(account["update_time"], "%H:%M").time()
            context.job_queue.run_daily(
                send_cash_update,
                time=update_time,
                chat_id=user_id,
                name="cash_update",
                data=account,
            )


def save_cash_watchers():
    with open(CASH_WATCHERS_FILE, "w") as f:
        json.dump(cash_watchers, f)


async def watch_cash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /watchCash <HH:MM> <your_maplelegends_id>"
        )
        return

    update_time = args[0]
    maplelegends_id = args[1]

    # Validate time format
    try:
        datetime.strptime(update_time, "%H:%M")
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:MM.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            username, cash_amount = await get_cash_amount(maplelegends_id, session)
    except Exception as e:
        await update.message.reply_text(f"Error fetching data: {str(e)}")
        return

    if user_id not in cash_watchers:
        cash_watchers[user_id] = []

    existing_entry = next(
        (item for item in cash_watchers[user_id] if item["id"] == maplelegends_id), None
    )

    if existing_entry:
        existing_entry["update_time"] = update_time
        await update.message.reply_text(
            f"Updated: You will receive daily cash updates for {username} at {update_time} UTC"
        )
    else:
        cash_watchers[user_id].append(
            {
                "id": maplelegends_id,
                "username": username,
                "last_cash": cash_amount,
                "update_time": update_time,
            }
        )
        await update.message.reply_text(
            f"You will now receive daily cash updates for {username} at {update_time} UTC"
        )

    save_cash_watchers()
    schedule_cash_updates(context)


async def send_cash_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.chat_id
    account = job.data

    maplelegends_id = account["id"]
    stored_username = account["username"]
    last_cash = account.get("last_cash", 0)

    try:
        async with aiohttp.ClientSession() as session:
            username, cash_amount = await get_cash_amount(maplelegends_id, session)
        difference = cash_amount - last_cash
        message = f"Vote Cash update for {username}: {cash_amount:,} ({difference:+,} since last check)"

        # Update the stored cash amount
        account["last_cash"] = cash_amount
        account["username"] = username
    except Exception as e:
        logger.error(f"Error getting cash for user {maplelegends_id}: {str(e)}")
        message = f"Error fetching data for {stored_username} (ID {maplelegends_id})"

    try:
        await context.bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        logger.error(f"Error sending cash update to user {user_id}: {str(e)}")

    save_cash_watchers()


async def get_cash_amount(user_id, session):
    """Helper function to get cash amount and username."""
    url = "https://maplelegends.com/my/account"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cookie": f"mlTheme=light; webpy_session_id={user_id}",
        "referer": "https://maplelegends.com/vote",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with session.get(url, headers=headers) as response:
        response.raise_for_status()
        text = await response.text()

    soup = BeautifulSoup(text, "html.parser")
    vote_cash_element = soup.select_one('div.col-md-6:-soup-contains("Vote Cash:") b')
    username_element = soup.select_one(
        "ul.nav.navbar-nav.pull-right li.visible-md.visible-lg a.spa"
    )

    if vote_cash_element and username_element:
        cash_amount = vote_cash_element.text.strip().replace(",", "")
        return username_element.text.strip(), int(float(cash_amount))
    else:
        raise ValueError(
            f"Unable to find Vote Cash or username information for user ID {user_id}"
        )


async def get_cash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display the vote cash for a given user ID."""
    if not context.args:
        await update.message.reply_text(
            "Please provide a user ID. Usage: /getCash <id>"
        )
        return

    user_id = context.args[0]

    try:
        async with aiohttp.ClientSession() as session:
            username, vote_cash = await get_cash_amount(user_id, session)
        await update.message.reply_text(f"Vote Cash amount for {username}: {vote_cash}")
    except ValueError as e:
        await update.message.reply_text(str(e))
    except Exception as e:
        await update.message.reply_text(f"Error fetching data: {str(e)}")


async def update_cash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)

    if user_id not in cash_watchers or not cash_watchers[user_id]:
        await update.message.reply_text(
            "You haven't registered any accounts to watch. Use /watchCash to add accounts."
        )
        return

    # Send an initial message
    message = await update.message.reply_text("Fetching cash amounts...")

    async def fetch_cash(entry):
        async with aiohttp.ClientSession() as session:
            maplelegends_id = entry["id"]
            stored_username = entry["username"]
            last_cash = entry.get("last_cash", 0)
            try:
                async with aiohttp.ClientSession() as session:
                    username, cash_amount = await get_cash_amount(
                        maplelegends_id, session
                    )
                difference = cash_amount - last_cash
                result = (
                    f"{username}: {cash_amount:,} ({difference:+,} since last check)\n"
                )
                entry["last_cash"] = cash_amount
                entry["username"] = username
                return result
            except Exception as e:
                logger.error(f"Error getting cash for user {maplelegends_id}: {str(e)}")
                return (
                    f"{stored_username} (ID {maplelegends_id}): Error fetching data\n"
                )

    # Create tasks for all cash fetching operations
    tasks = [fetch_cash(entry) for entry in cash_watchers[user_id]]

    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)

    # Combine results
    result_message = "Current Vote Cash amounts:\n" + "".join(results)

    # Update the message with the results
    await message.edit_text(result_message)
    save_cash_watchers()  # Save the updated cash amounts


# Modify your command handler to use create_task
async def handle_update_cash(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    asyncio.create_task(update_cash(update, context))
