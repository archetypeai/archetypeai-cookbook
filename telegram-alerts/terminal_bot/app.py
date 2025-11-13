#!/usr/bin/env python3
"""
Smart Monitor (Telegram Alerts)
Streams RTSP or a pre-uploaded video file to Newton’s Activity Monitor Lens.
Sends Telegram alerts when the Lens output contains “Alert: …”.
"""

import logging
import os
import requests
from pprint import pformat
from archetypeai.api_client import ArchetypeAI

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Banner ----------
BANNER = r"""
███╗   ██╗███████╗██╗    ██╗████████╗ ██████╗ ███╗   ██╗     █████╗ ██╗
████╗  ██║██╔════╝██║    ██║╚══██╔══╝██╔═══██╗████╗  ██║    ██╔══██╗██║
██╔██╗ ██║█████╗  ██║ █╗ ██║   ██║   ██║   ██║██╔██╗ ██║    ███████║██║
██║╚██╗██║██╔══╝  ██║███╗██║   ██║   ██║   ██║██║╚██╗██║    ██╔══██║██║
██║ ╚████║███████╗╚███╔███╔╝   ██║   ╚██████╔╝██║ ╚████║    ██║  ██║██╗
╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝    ╚═╝    ╚═════╝ ╚═╝  ╚═══╝    ╚═╝  ╚═╝╚═╝
"""
print(BANNER)

# ---------- Lens Config ----------
DEFAULT_INSTRUCTION = (
    "STOP. FOLLOW THIS EXACT FORMAT: Step 1: Write <scan> I see in this video: "
    "then list ALL detected objects, vehicles, people, animals, buildings, and their "
    "visual or behavioral attributes (colors, shapes, positions, actions). Then close "
    "with </scan>. Step 2: Write Search result: and analyze if the item or event being "
    "searched for is present in your scan. Step 3: If the searched-for item is not found, "
    "write: No alerts: short description of what was detected, max 15 words. "
    "If the searched-for item is present, it is VERY IMPORTANT THAT YOU WRITE THIS: "
    "Alert: short description of what was detected, max 15 words ONLY return one of the above. "
    "Do not describe anything else."
)
DEFAULT_STEP_SIZE = 30
DEFAULT_TEMPORAL_FOCUS = 5
DEFAULT_MAX_NEW_TOKENS = 256

# ---------- Telegram Config ----------
BOT_TOKEN = "YOUR_BOT_TOCKEN"
CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_alert(message: str) -> None:
    """Send a Telegram text alert (best-effort)."""
    if not BOT_TOKEN or "YOUR_TELEGRAM_BOT_TOKEN" in BOT_TOKEN:
        logging.warning("⚠️ Telegram BOT token not set; skipping alert send.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
        logging.info("✅ Telegram alert sent!")
    except Exception as e:
        logging.error(f"❌ Failed to send Telegram alert: {e}")

# ---------- State ----------
last_alert_state = False  # toggles when we first see an “Alert: …” line

def session_callback(session_id, session_endpoint, client: ArchetypeAI, args: dict) -> None:
    """Main function to run the logic of a custom lens session."""
    global last_alert_state

    # Create a SSE reader to read the output of the lens.
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])

    for event in sse_reader.read(block=True):
        logging.info(event)

        # --- Alert detection
        if isinstance(event, dict) and event.get("type") == "inference.result":
            resp_list = event.get("event_data", {}).get("response", [])
            if resp_list:
                text = resp_list[0]
                is_alert = "alert:" in text.lower()

                if is_alert and not last_alert_state:
                    alert_text = text.split("Alert:", 1)[-1].strip()
                    logging.info(f"🚨 Alert detected (state changed): {alert_text}")
                    send_telegram_alert(f"🚨 Alert: {alert_text}")

                last_alert_state = is_alert

    # Close any active reader.
    sse_reader.close()

# ---------- Main ----------
def main():
    print("=== Smart Monitor Setup ===")
    api_key = os.getenv("ATAI_API_KEY", "").strip() or input("Enter your API Key: ").strip()
    api_endpoint = os.getenv("ATAI_API_ENDPOINT", "").strip() or input("Enter your API Endpoint (Press Enter for default): ").strip() or ArchetypeAI.get_default_endpoint()
    if not api_key:
        print("API key is required."); return

    input_type = ""
    while input_type not in ("rtsp", "video"):
        input_type = input("Input type (rtsp / video): ").strip().lower()

    rtsp_url, video_file_id = None, None
    if input_type == "rtsp":
        rtsp_url = input("Enter RTSP URL: ").strip()
        if not rtsp_url:
            print("RTSP URL is required for rtsp input."); return
    else:
        video_file_id = input("Enter video file ID (already uploaded under your API key - including .mp4): ").strip()
        if not video_file_id:
            print("Video file ID is required for video input."); return

    focus = input("Enter focus (what to look for): ").strip() or "Describe the video."

    args = {
        "api_key": api_key,
        "rtsp_url": rtsp_url,
        "video_file_id": video_file_id,
        "input_type": input_type,
        "focus": focus,
        "instruction": DEFAULT_INSTRUCTION,
        "max_run_time_sec": 600.0,
        "api_endpoint": api_endpoint,
        "step_size": DEFAULT_STEP_SIZE,
        "temporal_focus": DEFAULT_TEMPORAL_FOCUS,
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS
    }

    client = ArchetypeAI(args["api_key"], api_endpoint=args["api_endpoint"])
    logging.info("▶️ Starting monitoring session…")
    send_telegram_alert("▶️ Smart monitoring started…")

    # Handle file upload if using video input
    if input_type == "video":
        # Note: video_file_id is expected to be already uploaded file ID
        # If it's a file path, this would need to be modified
        file_id = video_file_id
        input_streams_config = f"""
            - stream_type: video_file_reader
              stream_config:
                file_id: {file_id}
                step_size: {args['step_size']}"""
    else:
        input_streams_config = f"""
            - stream_type: rtsp_video_reader
              stream_config:
                rtsp_url: "{args['rtsp_url']}"
                target_image_size: [360, 640]
                target_frame_rate_hz: 1.0"""

    # Create a custom lens and automatically launch the lens session.
    client.lens.create_and_run_lens(f"""
       lens_name: Custom Telegram Activity Monitor
       lens_config:
        model_parameters:
            model_version: Newton::c2_3_7b_2508014e10af56
            instruction: "{args['instruction']}"
            focus: "{args['focus']}"
            temporal_focus: {args['temporal_focus']}
            max_new_tokens: {args['max_new_tokens']}
        input_streams:{input_streams_config}
        output_streams:
            - stream_type: server_sent_events_writer
    """, session_callback, client=client, args=args)

if __name__ == "__main__":
    main()
