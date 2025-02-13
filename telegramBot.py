import json
import logging
import os

import requests
from dotenv import load_dotenv
from telegram import ForceReply, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from cash_functions import (
    get_cash,
    handle_update_cash,
    load_cash_watchers,
    remove_cash_watcher,
    schedule_cash_updates,
    watch_cash,
)

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


def load_watching_users():
    global watching_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            watching_users = set(json.load(f))


def save_watching_users():
    with open(USERS_FILE, "w") as f:
        json.dump(list(watching_users), f)


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
        "/watchCash <HH:MM> <your_maplelegends_id> - Daily updates of your vote cash amount at <HH:MM> UTC\n"
        "/removeCashWatcher <username> - Remove a specific cash watcher\n"
        "/updateCash - Get an immediate update of cash amounts for all your registered accounts\n"
        "/help - Show this help message\n"
    )
    await update.message.reply_text(help_text)


async def invalid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to invalid commands or messages."""
    await update.message.reply_text(
        "Sorry, I don't understand that command or message. Use /help to see available commands."
    )


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
    application.add_handler(CommandHandler("updateCash", handle_update_cash))
    application.add_handler(CommandHandler("removeCashWatcher", remove_cash_watcher))
    application.add_handler(MessageHandler(filters.TEXT, invalid_command))

    # Schedule cash updates
    schedule_cash_updates(application)

    # Set up job to check server status every minute
    application.job_queue.run_repeating(check_server_status, interval=60)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)
