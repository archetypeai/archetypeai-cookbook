# Smart Monitor (Terminal + Telegram Alerts)

Interactive terminal app that monitors video streams and sends Telegram alerts when specific activities are detected.

## Requirements

- Python 3.9+
- [ArchetypeAI Python client](https://github.com/archetypeai/python-client)

Install dependencies:
```bash
pip install requests
```

## Configuration

Update these variables in `app.py`:
- `BOT_TOKEN`: Your Telegram bot token
- `CHAT_ID`: Your Telegram chat ID

## Usage

```bash
python app.py
```

## Interactive Prompts

1. **API Key**: Your ArchetypeAI API key
2. **Input Type**: Choose `rtsp` (camera stream) or `video` (uploaded file ID)
3. **Source**: 
   - For RTSP: Camera stream URL
   - For video: File ID from previously uploaded video
4. **Focus**: What to monitor for (e.g., "person at door", "package delivery")

## Example Session

```
=== Smart Monitor Setup ===
Enter your API Key: your-api-key
Input type (rtsp / video): rtsp
Enter RTSP URL: rtsp://camera.local:554/stream
Enter focus (what to look for): person at the door

▶️ Starting monitoring session…
```

Telegram alerts will be sent when the focus activity is detected.

## How it works

1. Connects to Newton's Activity Monitor Lens
2. Streams video from RTSP camera or uploaded video file
3. Analyzes content based on your focus phrase
4. Sends Telegram notification when alerts trigger
5. Continues monitoring until session completes or times out