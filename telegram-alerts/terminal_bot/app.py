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
LENS_ID = "lns-fd669361822b07e2-bc718aa3fdf0b3b7"

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

# ---------- Session Handling ----------
def session_fn(session_id, session_endpoint, client: ArchetypeAI, args: dict) -> None:
    global last_alert_state

    # Input stream (RTSP or already-uploaded video file ID)
    if args["input_type"] == "rtsp":
        event = {
            "type": "input_stream.set",
            "event_data": {
                "stream_type": "rtsp_video_reader",
                "stream_config": {
                    "rtsp_url": args["rtsp_url"],
                    "target_image_size": [360, 640],
                    "target_frame_rate_hz": 1.0,
                }
            }
        }
    else:
        event = {
            "type": "input_stream.set",
            "event_data": {
                "stream_type": "video_file_reader",
                "stream_config": {
                    "file_id": args["video_file_id"],
                    "step_size": 60,
                    "window_size": 1,
                }
            }
        }
    resp = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Stream response:\n{pformat(resp, indent=4)}")

    # --- Focus & instruction
    event = {
        "type": "session.modify",
        "event_data": {
            "focus": args["focus"],
            "max_new_tokens": 256,
            "instruction": args["instruction"],
        }
    }
    resp = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Instruction response:\n{pformat(resp, indent=4)}")

    # Output stream
    event = {
        "type": "output_stream.set",
        "event_data": {"stream_type": "server_side_events_writer", "stream_config": {}}
    }
    resp = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Output stream response:\n{pformat(resp, indent=4)}")

    # --- SSE Reader
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])
    for ev in sse_reader.read(block=True):
        logging.info(ev)

        # --- Alert detection
        if isinstance(ev, dict) and ev.get("type") == "inference.result":
            resp_list = ev.get("event_data", {}).get("response", [])
            if resp_list:
                text = resp_list[0]
                is_alert = "alert:" in text.lower()

                if is_alert and not last_alert_state:
                    alert_text = text.split("Alert:", 1)[-1].strip()
                    logging.info(f"🚨 Alert detected (state changed): {alert_text}")
                    send_telegram_alert(f"🚨 Alert: {alert_text}")

                last_alert_state = is_alert

    sse_reader.close()

# ---------- Main ----------
def main():
    print("=== Smart Monitor Setup ===")
    api_key = os.getenv("ARCHETYPE_API_KEY", "").strip() or input("Enter your API Key: ").strip()
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
        video_file_id = input("Enter video file ID (already uploaded under your API key): ").strip()
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
    }

    client = ArchetypeAI(api_key, api_endpoint=ArchetypeAI.get_default_endpoint())
    logging.info("▶️ Starting monitoring session…")
    send_telegram_alert("▶️ Smart monitoring started…")

    client.lens.create_and_run_session(LENS_ID, session_fn, auto_destroy=True, client=client, args=args)

if __name__ == "__main__":
    main()
