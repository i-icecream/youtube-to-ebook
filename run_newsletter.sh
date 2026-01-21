#!/bin/bash
# Runner script for YouTube Newsletter
# This script is called by launchd on a schedule

# Change to the project directory
cd /Users/bytedance/youtube-newsletter

# Run the newsletter generator
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/bytedance/youtube-newsletter/main.py >> /Users/bytedance/youtube-newsletter/logs/newsletter.log 2>&1

# Add a timestamp to the log
echo "--- Completed at $(date) ---" >> /Users/bytedance/youtube-newsletter/logs/newsletter.log
