"""
Activity Monitor Quickstart
Interactive activity monitoring using Newton's Activity Monitor Lens for video or RTSP analysis
"""

import logging
import os
import signal
import sys
from archetypeai.api_client import ArchetypeAI

logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Banner ----------
BANNER = r"""
███╗   ██╗███████╗██╗    ██╗████████╗ ██████╗ ███╗   ██╗     █████╗ ██╗
████╗  ██║██╔════╝██║    ██║╚══██╔══╝██╔═══██╗████╗  ██║    ██╔══██╗██║
██╔██╗ ██║█████╗  ██║ █╗ ██║   ██║   ██║   ██║██╔██╗ ██║    ███████║██║
██║╚██╗██║██╔══╝  ██║███╗██║   ██║   ██║   ██║██║╚██╗██║    ██╔══██║██║
██║ ╚████║███████╗╚███╔███╔╝   ██║   ╚██████╔╝██║ ╚████║    ██║  ██║██╗
╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝    ╚═╝    ╚═════╝ ╚═╝  ╚═══╝    ╚═╝  ╚═╝╚═╝
"""
def c(text, r=164, g=186, b=250):
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

# ---------- Setup ----------
DEFAULT_LENS_ID = "lns-fd669361822b07e2-bc718aa3fdf0b3b7"
DEFAULT_INSTRUCTION = "Answer the following question about the video in less than 15 words:"
DEFAULT_MAX_RUN_SEC = 600.0
DEFAULT_MAX_NEW_TOKENS = 256
DEFAULT_STEP_SIZE = 60
DEFAULT_WINDOW_SIZE = 60

# ---------- Interactive inputs ----------
def get_user_inputs() -> dict:
    print(c(BANNER))
    print("\n=== Activity Monitor ===\n")

    api_key = os.getenv("ARCHETYPE_API_KEY", "").strip() or input("Enter your ArchetypeAI API key: ").strip()
    if not api_key:
        print("Error: API key is required."); sys.exit(1)

    # Input type
    input_type = ""
    while input_type not in ("video", "rtsp"):
        input_type = input("Input type (video/rtsp): ").strip().lower()

    video_file_path = None
    rtsp_url = None
    if input_type == "video":
        while True:
            p = input("Enter path to video file: ").strip().strip("'\"")
            if os.path.exists(p):
                video_file_path = p; break
            print(f"Error: '{p}' not found.")
    else:
        while True:
            u = input("Enter RTSP URL: ").strip()
            if u.lower().startswith(("rtsp://", "rtsps://")):
                rtsp_url = u; break
            print("Please enter a valid rtsp:// or rtsps:// URL.")

    focus = input("\nWhat would you like to know about the video? ").strip() or "Describe the video."
    instruction = DEFAULT_INSTRUCTION

    return {
        "api_key": api_key,
        "input_type": input_type,
        "video_file_path": video_file_path,
        "rtsp_url": rtsp_url,
        "focus": focus,
        "instruction": instruction,
        "max_run_time_sec": DEFAULT_MAX_RUN_SEC,
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
        "lens_id": DEFAULT_LENS_ID,
        "video_file_id": None,          # filled later if video
        "step_size": DEFAULT_STEP_SIZE,
        "window_size": DEFAULT_WINDOW_SIZE,
    }

# ---------- Event builders ----------
def build_input_event(args: dict) -> dict:
    if args["input_type"] == "rtsp":
        return {
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
        return {
            "type": "input_stream.set",
            "event_data": {
                "stream_type": "video_file_reader",
                "stream_config": {
                    "file_id": args["video_file_id"],
                    "step_size": args["step_size"],
                    "window_size": args["window_size"],
                }
            }
        }

def build_focus_event(args: dict) -> dict:
    return {
        "type": "session.modify",
        "event_data": {
            "focus": args["focus"],
            "max_new_tokens": args["max_new_tokens"],
            "instruction": args["instruction"]
        }
    }

def build_output_event() -> dict:
    return {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "server_side_events_writer",
            "stream_config": {},
        }
    }

# ---------- Session ----------
def session_fn(session_id: str, session_endpoint: str, client: ArchetypeAI, args: dict) -> None:
    print(f"Session created: {session_id}")

    # If using a video file, upload it now (after session start)
    if args["input_type"] == "video" and args.get("video_file_path"):
        print(f"Uploading video: {args['video_file_path']}")
        try:
            resp = client.files.local.upload(args["video_file_path"])
            args["video_file_id"] = resp.get("file_id")
            if not args["video_file_id"]:
                print("Error: no file_id returned."); return
        except Exception as e:
            print(f"Error: Failed to upload video: {e}")
            return

    # Configure streams and focus
    client.lens.sessions.process_event(session_id, build_input_event(args))
    client.lens.sessions.process_event(session_id, build_focus_event(args))
    client.lens.sessions.process_event(session_id, build_output_event())

    # SSE reader
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])

    print(f"\nMonitoring started — looking for: '{args['focus']}'")
    print("Press Ctrl+C to stop\n")

    stop = {"flag": False}
    def _sigint(_s, _f): stop["flag"] = True
    signal.signal(signal.SIGINT, _sigint)

    try:
        for ev in sse_reader.read(block=True):
            if stop["flag"]:
                break
            if isinstance(ev, dict) and ev.get("type") == "inference.result":
                ed = ev.get("event_data", {})
                resp = ed.get("response") or []
                ts = ed.get("query_metadata", {}).get("sensor_timestamp", "N/A")
                if resp and isinstance(resp, list):
                    print(f"{ts}: {resp[0]}")
    finally:
        sse_reader.close()
        print("Stopped.")

# ---------- Main ----------
def main():
    args = get_user_inputs()
    client = ArchetypeAI(args["api_key"], api_endpoint=ArchetypeAI.get_default_endpoint())

    print("\n--- Configuration Summary ---")
    print(f"Input:  {args['input_type'].upper()}")
    if args['input_type'] == 'rtsp':
        print(f"RTSP:   {args['rtsp_url']}")
    else:
        print(f"Video:  {args['video_file_path']}")
    print(f"Focus:  {args['focus']}")

    input("\nPress Enter to start monitoring...")

    # Start session;
    client.lens.create_and_run_session(args["lens_id"], session_fn, auto_destroy=True, client=client, args=args)
    print("Session finished.")

if __name__ == "__main__":
    main()
