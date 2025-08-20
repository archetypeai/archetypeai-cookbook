# Telegram Activity Monitor Bot

Control Newton's Activity Monitor via Telegram commands. Detects alerts in video streams and sends notifications.

## Requirements

- Python 3.9+
- [ArchetypeAI Python client](https://github.com/archetypeai/python-client)
- python-telegram-bot library

Install dependencies:
```bash
pip install python-telegram-bot
```

## Configuration

Update these variables in `app.py`:
- `BOT_TOKEN`: Your Telegram bot token
- `CHAT_ID`: Your Telegram chat ID

## Usage

```bash
python app.py
```

## Telegram Commands

- `/start` - Show available commands
- `/start_monitoring <api_key> <rtsp|video> <url_or_id> <focus>` - Start monitoring
- `/stop_monitoring` - Stop current session
- `/change_focus <new_focus>` - Update monitoring focus
- `/status` - Check if monitoring is active

## Example

```
/start_monitoring your-api-key rtsp rtsp://camera.local:554/stream person at the door
/start_monitoring your-api-key video delivery.mp4 package delivered
```

Bot will send Telegram alerts when the specified activity is detected.

## How it works

1. Connects to Newton's Activity Monitor Lens
2. Streams video from RTSP camera or video file
3. Analyzes content based on your focus phrase
4. Sends Telegram notification when alerts trigger