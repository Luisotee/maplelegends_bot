# MapleLegends Telegram Bot

This Telegram bot provides various functionalities for MapleLegends players, including server status updates, character stats retrieval, and vote cash tracking.

## Features

- Check server status and receive notifications when the server goes offline or comes back online
- Retrieve character stats and avatar
- Check and track vote cash amounts
- Get current number of online users

## Commands

- `/start`: Start the bot and receive a welcome message
- `/help`: Show the help message with available commands
- `/serverStatus`: Display the current number of players on the server and indicate whether the server is active or inactive
- `/watchServerStatus`: Toggle server status notifications on/off
- `/getStats <CharacterName>`: Get stats and avatar for a specific character
- `/getCash <id>`: Get the amount of vote cash for a given user ID
- `/watchCash <your_maplelegends_id>`: Toggle daily cash updates on/off

## Usage

### User ID for Cash

To get the user ID to use with `/getCash <id>` and `/watchCash <your_maplelegends_id>`, follow these steps:

1. Go to `https://maplelegends.com/`
2. Log in with the account you want to check the cash for
3. Open dev tools, usually with `F12`
4. Go to the Network tab
5. Navigate to "My Account" and "Account Details" on the website
6. Look for a request called `account` in the Network tab
7. Click on it and go to Headers; find `Set-Cookie` in the Response Headers, your ID is the `webpy_session_id` number
