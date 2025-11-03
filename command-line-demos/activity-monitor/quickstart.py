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
def colorize_text(text: str, red: int = 164, green: int = 186, blue: int = 250) -> str:
    return f"\033[38;2;{red};{green};{blue}m{text}\033[0m"

# ---------- Setup ----------
DEFAULT_INSTRUCTION = "Answer the following question about the video in less than 15 words:"
DEFAULT_MAX_RUN_SEC = 600.0
DEFAULT_MAX_NEW_TOKENS = 256
DEFAULT_STEP_SIZE = 30
DEFAULT_TEMPORAL_FOCUS = 5

# ---------- Interactive inputs ----------
def get_user_inputs() -> dict:
    print(colorize_text(BANNER))
    print("\n=== Activity Monitor ===\n")

    api_key = os.getenv("ATAI_API_KEY", "").strip() or input("Enter your ArchetypeAI API key: ").strip()
    api_endpoint = os.getenv("ATAI_API_ENDPOINT", "").strip() or input("Enter your API Endpoint (Press Enter for default): ").strip() or ArchetypeAI.get_default_endpoint()
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

    focus = input("\nEnter focus (what to look for): ").strip() or "Describe the video."

    temporal_focus_input = input(f"Temporal focus (default: {DEFAULT_TEMPORAL_FOCUS}): ").strip()
    temporal_focus = int(temporal_focus_input) if temporal_focus_input.isdigit() else DEFAULT_TEMPORAL_FOCUS

    return {
        "api_key": api_key,
        "input_type": input_type,
        "video_file_path": video_file_path,
        "rtsp_url": rtsp_url,
        "focus": focus,
        "instruction": DEFAULT_INSTRUCTION,
        "max_run_time_sec": DEFAULT_MAX_RUN_SEC,
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
        "step_size": DEFAULT_STEP_SIZE,
        "temporal_focus": temporal_focus,
        "api_endpoint": api_endpoint,
    }


def session_callback(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

    # Create a SSE reader to read the output of the lens.
    sse_reader = client.lens.sessions.create_sse_consumer(
        session_id, max_read_time_sec=args["max_run_time_sec"])

    print(f"\nMonitoring started — looking for: '{args['focus']}'")
    print("Press Ctrl+C to stop\n")

    stop = {"flag": False}
    def _sigint(_s, _f): stop["flag"] = True
    signal.signal(signal.SIGINT, _sigint)

    try:
        # Read events from the SSE stream until either the last message is
        # received or the max read time has been reached.
        for event in sse_reader.read(block=True):
            if stop["flag"]:
                break
            if isinstance(event, dict) and event.get("type") == "inference.result":
                ed = event.get("event_data", {})
                resp = ed.get("response") or []
                ts = ed.get("query_metadata", {}).get("sensor_timestamp", "N/A")
                if resp and isinstance(resp, list):
                    print(f"{ts}: {resp[0]}")
    finally:
        # Close any active reader.
        sse_reader.close()
        print("Stopped.")

# ---------- Main ----------
def main():
    args = get_user_inputs()
    client = ArchetypeAI(args["api_key"], api_endpoint=args["api_endpoint"])

    print("\n--- Configuration Summary ---")
    print(f"API Endpoint: {args['api_endpoint']} ")
    print(f"Input:  {args['input_type'].upper()}")
    if args['input_type'] == 'rtsp':
        print(f"RTSP:   {args['rtsp_url']}")
    else:
        print(f"Video:  {args['video_file_path']}")
    print(f"Focus:  {args['focus']}")

    input("\nPress Enter to start monitoring...")

    # Upload the video file to the archetype platform if using video input.
    if args["input_type"] == "video":
        print(f"Uploading video: {args['video_file_path']}")
        try:
            file_response = client.files.local.upload(args["video_file_path"])
            video_file_id = file_response["file_id"]
        except Exception as e:
            print(f"Error: Failed to upload video: {e}")
            return

        input_streams_config = f"""
            - stream_type: video_file_reader
              stream_config:
                file_id: {video_file_id}
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
       lens_name: Custom Activity Monitor
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
    print("Session finished.")

if __name__ == "__main__":
    main()
