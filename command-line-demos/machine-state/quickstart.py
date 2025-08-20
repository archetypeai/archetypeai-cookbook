"""
Machine State Quickstart
Streams a CSV file to a Newton Lens with one-shot class examples and prints predictions.
"""

import logging
import os
import signal
import sys
from pathlib import Path

from archetypeai.api_client import ArchetypeAI

# ---------- Logging ----------
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
def c(text, r=164, g=186, b=250): return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

# ---------- Defaults ----------
DEFAULT_LENS_ID = "lns-1d519091822706e2-bc108andqxf8b4os"
DEFAULT_API_ENDPOINT = "https://api.archetypeai.dev/v0.5"
DEFAULT_MAX_RUN_SEC = 600.0
DEFAULT_WINDOW_SIZE = 1024
DEFAULT_STEP_SIZE = 1024  # no overlap

# ---------- Event builders ----------
def build_session_modify_event(input_n_shot: dict, window_size: int, step_size: int) -> dict:
    return {
        "type": "session.modify",
        "event_data": {
            "input_n_shot": input_n_shot,
            "csv_configs": {
                "timestamp_column": "timestamp",
                "data_columns": ["a1", "a2", "a3", "a4"],
                "window_size": window_size,
                "step_size": step_size,
            }
        }
    }

def build_input_event_csv(file_id: str, window_size: int, step_size: int) -> dict:
    return {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "csv_file_reader",
            "stream_config": {
                "file_id": file_id,
                "window_size": window_size,
                "step_size": step_size,
                "loop_recording": False,
                "output_format": ""
            }
        }
    }

def build_output_event() -> dict:
    return {
        "type": "output_stream.set",
        "event_data": {"stream_type": "server_side_events_writer", "stream_config": {}}
    }

# ---------- Interactive inputs ----------
def get_user_inputs() -> dict:
    print(c(BANNER))
    print("\n=== Machine State Lens ===\n")

    api_key = os.getenv("ARCHETYPE_API_KEY", "").strip() or input("Enter your API key: ").strip()
    if not api_key:
        print("Error: API key is required."); sys.exit(1)

    # Data CSV
    while True:
        data_file_path = input("Enter path to CSV to analyze: ").strip().strip("'\"")
        if os.path.exists(data_file_path) and data_file_path.lower().endswith(".csv"):
            break
        print("Error: file not found or not a .csv — try again.")

    # Focus CSVs 
    print("\n--- Add Focus Files ---")
    print("Provide CSV example(s) for each class (e.g., healthy.csv -> class 'healthy').")
    print("Type 'done' when finished.\n")

    focus_files = {}
    while True:
        p = input("Focus CSV path (or 'done'): ").strip().strip("'\"")
        if p.lower() == "done":
            if not focus_files:
                print("Add at least one focus file."); continue
            break
        if not (os.path.exists(p) and p.lower().endswith(".csv")):
            print("Error: file not found or not a .csv — try again."); continue
        cls = Path(p).stem.lower()
        focus_files[cls] = p
        print(f" Added: class '{cls}' from {Path(p).name}")

    # Window/step (minimal prompts)
    ws = input(f"\nWindow size [default {DEFAULT_WINDOW_SIZE}]: ").strip()
    ss = input(f"Step size   [default {DEFAULT_STEP_SIZE}]: ").strip()
    window_size = int(ws) if ws.isdigit() else DEFAULT_WINDOW_SIZE
    step_size = int(ss) if ss.isdigit() else DEFAULT_STEP_SIZE

    return {
        "api_key": api_key,
        "data_file_path": data_file_path,
        "focus_files": focus_files,
        "window_size": window_size,
        "step_size": step_size,
        "lens_id": DEFAULT_LENS_ID,
        "api_endpoint": DEFAULT_API_ENDPOINT,
        "max_run_time_sec": DEFAULT_MAX_RUN_SEC,
    }

# ---------- Session  ----------
def session_fn(session_id: str, session_endpoint: str, client: ArchetypeAI, args: dict) -> None:
    print(f"Session created: {session_id}")

    # Upload focus CSVs -> input_n_shot map
    input_n_shot = {}
    for cls, p in args["focus_files"].items():
        r = client.files.local.upload(p)
        input_n_shot[cls] = r["file_id"]

    # Upload data CSV
    data_resp = client.files.local.upload(args["data_file_path"])
    data_file_id = data_resp["file_id"]

    # Configure lens & streams
    client.lens.sessions.process_event(session_id, build_session_modify_event(input_n_shot, args["window_size"], args["step_size"]))
    client.lens.sessions.process_event(session_id, build_input_event_csv(data_file_id, args["window_size"], args["step_size"]))
    client.lens.sessions.process_event(session_id, build_output_event())

    # SSE reader (blocking, same style as your Activity Monitor)
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])

    print("\nStreaming… Press Ctrl+C to stop.\n")
    stop = {"flag": False}
    def _sigint(_s, _f): stop["flag"] = True
    signal.signal(signal.SIGINT, _sigint)

    try:
        for event in sse_reader.read(block=True):
            if stop["flag"]:
                break
            if isinstance(event, dict) and event.get("type") == "inference.result":
                ed = event.get("event_data", {}) or {}
                result = ed.get("response")
                meta = ed.get("query_metadata") or {}
                ts = meta.get("query_timestamp", "N/A")
                if result is not None:
                    print(f"[{ts}] → Predicted class: {result}")
    finally:
        sse_reader.close()
        print("Stopped.")

# ---------- Main ----------
def main():
    args = get_user_inputs()

    # Client
    client = ArchetypeAI(args["api_key"], api_endpoint=args["api_endpoint"])

    print("\n--- Configuration Summary ---")
    print(f"Lens ID:      {args['lens_id']}")
    print(f"API Endpoint: {args['api_endpoint']}")
    print(f"Data file:    {args['data_file_path']}")
    print(f"Classes:      {len(args['focus_files'])}")
    for cls, p in args["focus_files"].items():
        print(f"  - {cls}: {p}")

    input("\nPress Enter to start the analysis...")

    # Start session; uploads & config occur in session_fn
    client.lens.create_and_run_session(args["lens_id"], session_fn, auto_destroy=True, client=client, args=args)
    print("Session finished.")

if __name__ == "__main__":
    main()
