#!/bin/bash

# MedAssist Master Production Restart Script ⚙️🛡️🛸
# Usage: ./scripts/restart_prod.sh

echo "--- Starting MedAssist Production Sync & Restart ---"

# 1. Pull Latest Code
echo "📩 Fetching latest code from GitHub..."
git pull origin main

# 2. Activate Virtual Environment
source venv/bin/activate

# 3. Apply Migrations
echo "🏗️ Applying database migrations..."
python3 manage.py migrate

# 4. Kill Existing Processes
echo "🧹 Cleaning up old processes..."

# Kill Anything on Port 8000 (API)
API_PID=$(lsof -t -i:8000)
if [ ! -z "$API_PID" ]; then
    echo "  Killing existing API on port 8000 (PID: $API_PID)"
    kill -9 $API_PID
fi

# Kill Any Screen Sessions (Aggressive cleanup for duplicates)
echo "  Clearing old screen sessions..."
pkill -f "screen.*monitor" 2>/dev/null
pkill -f "screen.*api" 2>/dev/null
screen -wipe > /dev/null 2>&1

# 5. Start New Background Sessions
echo "🚀 Spinning up New Background Services..."

# Start API Server (Listening on 0.0.0.0)
screen -dmS api bash -c "source venv/bin/activate && python3 manage.py runserver 0.0.0.0:8000"
echo "  ✅ API Server Started (Port 8000)"

# Start Voice Reminder Monitor
screen -dmS monitor bash -c "source venv/bin/activate && python3 manage.py check_reminders --loop"
echo "  ✅ Voice Reminder Monitor Started"

echo "--------------------------------------------------------"
echo "--- FINAL STATUS CHECK ---"
lsof -i:8000
screen -ls
echo "--------------------------------------------------------"
echo "MedAssist is officially ONLINE & STABLE! 🦅🛡️🔥🏆"
