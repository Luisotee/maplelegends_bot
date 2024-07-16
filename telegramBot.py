import time
from dotenv import load_dotenv
import pytz
import requests
from telegram import ForceReply, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import logging
import json
import os
from bs4 import BeautifulSoup
from datetime import time
import pytz

load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Global variables to store shared count and lock
shared_count = None
count_lock = None
watching_users = set()
is_server_offline = False
USERS_FILE = "watching_users.json"
CASH_WATCHERS_FILE = "cash_watchers.json"
cash_watchers = {}


def load_watching_users():
    global watching_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            watching_users = set(json.load(f))


def load_cash_watchers():
    global cash_watchers
    if os.path.exists(CASH_WATCHERS_FILE):
        with open(CASH_WATCHERS_FILE, "r") as f:
            cash_watchers = json.load(f)
    else:
        cash_watchers = {}


def save_watching_users():
    with open(USERS_FILE, "w") as f:
        json.dump(list(watching_users), f)


async def watch_server_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle server status watching for the user."""
    user_id = update.effective_user.id

    if user_id in watching_users:
        watching_users.remove(user_id)
        await update.message.reply_text(
            "You will no longer receive server status notifications."
        )
    else:
        watching_users.add(user_id)
        await update.message.reply_text(
            "You will now receive server status notifications."
        )

    save_watching_users()  # Save the updated list


async def check_server_status(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check server status and notify users if necessary."""
    global is_server_offline
    with count_lock:
        count = shared_count.value

    if count < 10 and not is_server_offline:
        is_server_offline = True
        for user_id in watching_users:
            await context.bot.send_message(
                chat_id=user_id, text="Warning: Server is offline (player count < 10)!"
            )
    elif count >= 10 and is_server_offline:
        is_server_offline = False
        for user_id in watching_users:
            await context.bot.send_message(
                chat_id=user_id, text="Server is back online!"
            )


async def server_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current server status."""
    global is_server_offline
    with count_lock:
        count = shared_count.value

    if count < 10:
        status = "Offline"
    else:
        status = "Online"

    await update.message.reply_text(
        f"Server Status: {status}\nCurrent online users: {count}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "Available commands:\n\n"
        "/start - Start the bot and receive a welcome message\n"
        "/serverStatus - Show the current server status\n"
        "/watchServerStatus - Toggle server status notifications on/off\n"
        "/getStats <CharacterName> - Get stats and avatar for a specific character\n"
        "/getCash <id> - Get the amount of vote cash for a given user ID. You can learn about how to get the id in https://github.com/Luisotee/maplelegends_bot\n"
        "/watchCash <your_maplelegends_id> - Toggle daily cash updates on/off\n"
        "/help - Show this help message\n"
    )
    await update.message.reply_text(help_text)


async def invalid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to invalid commands or messages."""
    await update.message.reply_text(
        "Sorry, I don't understand that command or message. Use /help to see available commands."
    )


async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display character stats and avatar."""
    if not context.args:
        await update.message.reply_text(
            "Please provide a character name. Usage: /getStats <CharacterName>"
        )
        return

    character_name = context.args[0]
    stats_url = f"https://maplelegends.com/api/character?name={character_name}"
    avatar_url = f"https://maplelegends.com/api/getavatar?name={character_name}"

    try:
        # Fetch character stats
        stats_response = requests.get(stats_url)
        stats_response.raise_for_status()
        character_data = stats_response.json()

        if not character_data:
            await update.message.reply_text(
                f"No data found for character: {character_name}"
            )
            return

        # Prepare stats message
        stats_message = f"**Stats for {character_data['name']}:**\n"
        stats_message += f"• Level: {character_data['level']}\n"
        stats_message += f"• Gender: {character_data['gender']}\n"
        stats_message += f"• Job: {character_data['job']}\n"
        stats_message += f"• EXP: {character_data['exp']}\n"
        stats_message += f"• Guild: {character_data['guild'] or 'None'}\n"
        stats_message += f"• Quests Completed: {character_data['quests']}\n"
        stats_message += f"• Monster Cards: {character_data['cards']}\n"
        stats_message += f"• Donor: {'Yes' if character_data['donor'] else 'No'}\n"
        stats_message += f"• Fame: {character_data['fame']}"

        # Fetch avatar image
        avatar_response = requests.get(avatar_url)
        avatar_response.raise_for_status()

        # Send avatar image and stats message
        await update.message.reply_photo(
            photo=avatar_response.content, caption=stats_message, parse_mode="Markdown"
        )

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Error fetching character data: {str(e)}")


def save_cash_watchers():
    with open(CASH_WATCHERS_FILE, "w") as f:
        json.dump(cash_watchers, f)


async def watch_cash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    args = context.args

    if not args:
        await update.message.reply_text("Usage: /watchCash <your_maplelegends_id>")
        return

    maplelegends_id = args[0]

    try:
        username, cash_amount = await get_cash_amount(maplelegends_id)
    except Exception as e:
        await update.message.reply_text(f"Error fetching data: {str(e)}")
        return

    if user_id not in cash_watchers:
        cash_watchers[user_id] = []

    existing_entry = next(
        (item for item in cash_watchers[user_id] if item["id"] == maplelegends_id), None
    )

    if existing_entry:
        cash_watchers[user_id].remove(existing_entry)
        await update.message.reply_text(
            f"You will no longer receive daily cash updates for {username}"
        )
    else:
        cash_watchers[user_id].append(
            {"id": maplelegends_id, "username": username, "last_cash": cash_amount}
        )
        await update.message.reply_text(
            f"You will now receive daily cash updates for {username}"
        )

    if not cash_watchers[user_id]:
        del cash_watchers[user_id]

    save_cash_watchers()


async def send_daily_cash_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    for user_id, maplelegends_ids in cash_watchers.items():
        message = "Your current Vote Cash amounts:\n"
        for entry in maplelegends_ids:
            maplelegends_id = entry["id"]
            stored_username = entry["username"]
            last_cash = entry.get("last_cash", 0)  # Use 0 if last_cash is not present
            try:
                username, cash_amount = await get_cash_amount(maplelegends_id)
                difference = cash_amount - last_cash
                message += (
                    f"{username}: {cash_amount:,} ({difference:+,} since last check)\n"
                )

                # Update the stored cash amount
                entry["last_cash"] = cash_amount
                entry["username"] = username
            except Exception as e:
                logger.error(f"Error getting cash for user {maplelegends_id}: {str(e)}")
                message += (
                    f"{stored_username} (ID {maplelegends_id}): Error fetching data\n"
                )

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Error sending cash update to user {user_id}: {str(e)}")

    save_cash_watchers()  # Save the updated cash_watchers after processing all users


async def get_cash_amount(user_id):
    """Helper function to get cash amount and username."""
    url = "https://maplelegends.com/my/account"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cookie": f"mlTheme=light; webpy_session_id={user_id}",
        "referer": "https://maplelegends.com/vote",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
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
        username, vote_cash = await get_cash_amount(user_id)
        await update.message.reply_text(f"Vote Cash amount for {username}: {vote_cash}")
    except ValueError as e:
        await update.message.reply_text(str(e))
    except Exception as e:
        await update.message.reply_text(f"Error fetching data: {str(e)}")


def runTelegramBot(shared_count_param, count_lock_param) -> None:
    global shared_count, count_lock
    shared_count = shared_count_param
    count_lock = count_lock_param

    print("Telegram bot started")

    # Load watching users and cash watchers from files
    load_watching_users()
    load_cash_watchers()

    # Get the bot token from the environment variable
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("Telegram bot token not found in environment variables")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("watchServerStatus", watch_server_status))
    application.add_handler(CommandHandler("getStats", get_stats))
    application.add_handler(CommandHandler("getCash", get_cash))
    application.add_handler(CommandHandler("watchCash", watch_cash))
    application.add_handler(CommandHandler("serverStatus", server_status))
    application.add_handler(MessageHandler(filters.TEXT, invalid_command))

    # Set up job to check server status every minute
    application.job_queue.run_repeating(check_server_status, interval=60)

    # Set up job to send daily cash updates at 12 PM UTC
    application.job_queue.run_daily(
        send_daily_cash_updates, time=time(hour=3, minute=18, tzinfo=pytz.UTC)
    )
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)
