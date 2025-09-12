#!/bin/bash

# Check for virtual environment in the current directory
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please create one."
    exit 1
fi

# Run the job collector
echo "Starting Job Collector..."
python3 collector.py

# Keep the script running or exit
echo "Collector finished. Press Ctrl+C to exit."
wait
