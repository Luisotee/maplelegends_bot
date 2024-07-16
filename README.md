# MapleLegends Telegram Bot

This Telegram bot provides various functionalities for MapleLegends players, including server status updates, character stats retrieval, and vote cash tracking.

## Features

- Check server status and receive notifications when the server goes offline or comes back online
- Retrieve character stats and avatar
- Check and track vote cash amounts
- Get current number of online users

## Commands

- `/start` - Start the bot and receive a welcome message
- `/serverStatus` - Show the current server status
- `/watchServerStatus` - Toggle server status notifications on/off (tells you when the server is offline and when it's back online)
- `/getStats <CharacterName>` - Get stats and avatar for a specific character
- `/getCash <id>` - Get the amount of vote cash for a given user ID. You can learn about how to get the id in the end of this document
- `/watchCash <HH:MM> <your_maplelegends_id>` - Daily updates of your vote cash amount at `<HH:MM>` UTC
- `/removeCashWatcher <username>` - Remove a specific cash watcher
- `/updateCash` - Get an immediate update of cash amounts for all your registered accounts
- `/help` - Show this help message

## Usage

### User ID for Cash

To get the user ID to use with `/getCash <id>` and `/watchCash <your_maplelegends_id>`, follow these steps:

**NOTE:** The token you receive from this process is valid only until you log in to the same account again. To utilize multiple cash watches, you can log into an account in an incognito tab and avoid logging in to that account again on the website (_you can still log in to the game without resetting the token_). If you log into the account on the website again, you will need to set up another watch using the new token.

1. Go to `https://maplelegends.com/`
2. Log in with the account you want to check the cash for
3. Open dev tools, usually with `F12`
4. Go to the Network tab
5. Navigate to "My Account" and "Account Details" on the website
6. Look for a request called `account` in the Network tab
7. Click on it and go to Headers; find `Set-Cookie` in the Response Headers, your ID is the `webpy_session_id` number
