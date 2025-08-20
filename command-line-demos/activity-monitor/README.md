# Activity Monitor Quickstart

Interactive video analysis using language.

## Requirements

- Python 3.9+
- [ArchetypeAI Python client](https://github.com/archetypeai/python-client)

You can install the ArchetypeAI client by following the instructions in the repository linked above.

## Usage

```bash
python quickstart.py
```

## What it does

Analyzes video content and answers your questions about what's happening in the video.

## Interactive Prompts

1. **API Key**: Your ArchetypeAI API key
2. **Input Type**: Choose `video` (local file) or `rtsp` (camera stream)
3. **Source**: 
   - For video: Path to video file (drag & drop supported)
   - For RTSP: Camera stream URL
4. **Focus**: Your question about the video (e.g., "Is there a person?", "What's happening?")

## Example Session

```
=== Activity Monitor Quickstart ===

Enter your ArchetypeAI API key: your-key-here

Input type (video/rtsp): video
Enter path to video file: /path/to/security_footage.mp4

What should the monitor look for? (e.g., 'person entering', 'vehicle'): Is there anyone at the door?

--- Configuration Summary ---
Input: VIDEO
Video file: /path/to/security_footage.mp4
Focus: Is there anyone at the door?

Press Enter to start monitoring...

🔍 Monitoring started - Looking for: 'Is there anyone at the door?'

Response: No, the door area is empty. I can see a driveway and front yard but no person present.
Response: Yes, there is a person approaching the front door carrying a package.
```

## Output

The system provides natural language responses to your questions about the video content. Responses update as the video progresses (for files) or continuously (for RTSP streams).