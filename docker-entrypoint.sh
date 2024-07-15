#!/bin/bash

# Check if watching_users.json exists, if not, create it
if [ ! -f /app/watching_users.json ]; then
    echo "{}" > /app/watching_users.json
fi

# Check if cash_watchers.json exists, if not, create it
if [ ! -f /app/cash_watchers.json ]; then
    echo "{}" > /app/cash_watchers.json
fi

# Execute the CMD from the Dockerfile, e.g., start your Python application
exec "$@"