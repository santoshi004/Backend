#!/bin/bash

# MedAssist Master Production Restart Script ⚙️🛡️🛸
# Optimized for AWS EC2 & Screen Session Management

echo "--- Starting MedAssist Production Sync & Restart ---"

# 1. Pull Latest Code
echo "📩 Fetching latest code from GitHub..."
git pull origin main

# 2. Activate Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Error: venv directory not found!"
    exit 1
fi

# 3. Handle Migrations
echo "🏗️ Checking for database migrations..."
# Check if any new migrations need to be created (optional but recommended)
python3 manage.py makemigrations --check || {
    echo "⚠️ Warning: Detected model changes without migrations. Creating them now..."
    python3 manage.py makemigrations
}
python3 manage.py migrate

# 4. Aggressive Process Cleanup
echo "🧹 Cleaning up old processes and zombie screens..."

# A. Gracefully tell named screens to quit
screen -S api -X quit > /dev/null 2>&1
screen -S monitor -X quit > /dev/null 2>&1

# B. Kill anything still occupying Port 8000
API_PID=$(lsof -t -i:8000)
if [ ! -z "$API_PID" ]; then
    echo "  Killing lingering API on port 8000 (PID: $API_PID)"
    kill -9 $API_PID
fi

# C. Force kill any remaining python processes matching our apps
pkill -f "manage.py runserver" 2>/dev/null
pkill -f "manage.py check_reminders" 2>/dev/null

# D. Final wipe of "Dead" screen sockets
screen -wipe > /dev/null 2>&1

# 5. Start New Background Sessions
echo "🚀 Spinning up New Background Services..."

# Start API Server
# Using 'bash -c' ensures the venv is active inside the screen terminal
screen -dmS api bash -c "source venv/bin/activate && python3 manage.py runserver 0.0.0.0:8000"
echo "  ✅ API Server Started (Port 8000)"

# Start Voice Reminder Monitor
screen -dmS monitor bash -c "source venv/bin/activate && python3 manage.py check_reminders --loop"
echo "  ✅ Voice Reminder Monitor Started"

echo "--------------------------------------------------------"
echo "--- FINAL STATUS CHECK ---"
sleep 2 # Give screens a second to initialize
screen -ls
echo "--------------------------------------------------------"
echo "MedAssist is officially ONLINE & STABLE! 🦅🛡️🔥🏆"