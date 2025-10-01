"""
Machine State → Google Sheets
Streams a CSV into a Newton Lens with one-shot examples and logs predictions to Google Sheets.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import pickle

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from archetypeai.api_client import ArchetypeAI

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BANNER = r"""
███╗   ██╗███████╗██╗    ██╗████████╗ ██████╗ ███╗   ██╗     █████╗ ██╗
████╗  ██║██╔════╝██║    ██║╚══██╔══╝██╔═══██╗████╗  ██║    ██╔══██╗██║
██╔██╗ ██║█████╗  ██║ █╗ ██║   ██║   ██║   ██║██╔██╗ ██║    ███████║██║
██║╚██╗██║██╔══╝  ██║███╗██║   ██║   ██║   ██║██║╚██╗██║    ██╔══██║██║
██║ ╚████║███████╗╚███╔███╔╝   ██║   ╚██████╔╝██║ ╚████║    ██║  ██║██╗
╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝    ╚═╝    ╚═════╝ ╚═╝  ╚═══╝    ╚═╝  ╚═╝╚═╝
"""
print(BANNER)

# ---------- Defaults ----------
DEFAULT_LENS_ID = "lns-1d519091822706e2-bc108andqxf8b4os"
DEFAULT_API_ENDPOINT = "https://api.archetypeai.dev/v0.5"
DEFAULT_MAX_RUN_SEC = 600.0
DEFAULT_WINDOW_SIZE = 1024
DEFAULT_STEP_SIZE = 1024  # no overlap
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ---------- Google Sheets Logger ----------
class GoogleSheetsLogger:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.service = self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Sheets API using credentials.json/token.pickle."""
        creds = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError("credentials.json not found. See README for setup.")
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)
        return build("sheets", "v4", credentials=creds)

    def init_sheet(self):
        """Clear sheet and write headers."""
        try:
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id, range="A:Z"
            ).execute()
            headers = [[
                "Timestamp", "File Analyzed", "Window",
                "Predicted Class", "Confidence %", "All Scores",
                "Status", "Notes"
            ]]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range="A1:H1",
                valueInputOption="USER_ENTERED",
                body={"values": headers}
            ).execute()
            logging.info("✅ Sheet cleared and headers written.")
        except Exception as e:
            logging.error(f"Error initializing sheet: {e}")

    def parse_prediction_result(self, result):
        """Handle formats like ['broken', {'broken': 63.1, 'healthy': 36.9}] or simple strings."""
        try:
            if isinstance(result, list) and len(result) >= 2 and isinstance(result[1], dict):
                predicted = str(result[0])
                scores = result[1]
                conf = scores.get(predicted, 0.0)
                all_scores = ", ".join(f"{k}: {v:.1f}" for k, v in scores.items())
                return predicted, f"{conf:.1f}%", all_scores
            return str(result), "N/A", str(result)
        except Exception as e:
            logging.error(f"parse_prediction_result error: {e}")
            return str(result), "N/A", str(result)

    def log_result(self, file_name: str, window_num: int, predicted_result, status="Success", notes=""):
        """Append one row with parsed result."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pred, conf, all_scores = self.parse_prediction_result(predicted_result)
        row = [[ts, file_name, f"Window {window_num}", pred, conf, all_scores, status, notes]]
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range="A:H",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": row}
            ).execute()
            logging.info(f"Logged: {pred} ({conf}) @ window {window_num}")
        except Exception as e:
            logging.error(f"Error logging to sheet: {e}")

# ---------- Event Builders ----------
def build_session_modify_event(input_n_shot: dict, window_size: int, step_size: int) -> dict:
    return {
        "type": "session.modify",
        "event_data": {
            "input_n_shot": input_n_shot,
            "csv_configs": {
                "timestamp_column": "timestamp",
                "data_columns": ["a1", "a2", "a3", "a4"],
                "window_size": window_size,
                "step_size": step_size
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

# ---------- Interactive Inputs ----------
def get_user_inputs() -> dict:
    print("\n=== Machine State → Google Sheets ===\n")

    api_key = os.getenv("ATAI_API_KEY", "").strip() or input("Enter your ArchetypeAI API key: ").strip()
    if not api_key:
        print("Error: API key is required."); sys.exit(1)

    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip() or input("Enter your Google Sheets ID: ").strip()
    if not spreadsheet_id:
        print("Error: Google Sheets ID is required."); sys.exit(1)

    while True:
        data_file_path = input("Enter path to CSV to analyze: ").strip().strip("'\"")
        if os.path.exists(data_file_path) and data_file_path.lower().endswith(".csv"):
            break
        print("Error: file not found or not a .csv — try again.")

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

    window_size_input = input(f"\nWindow size [default {DEFAULT_WINDOW_SIZE}]: ").strip()
    step_size_input = input(f"Step size   [default {DEFAULT_STEP_SIZE}]: ").strip()

    window_size = int(window_size_input) if window_size_input.isdigit() else DEFAULT_WINDOW_SIZE
    step_size = int(step_size_input) if step_size_input.isdigit() else DEFAULT_STEP_SIZE

    return {
        "api_key": api_key,
        "spreadsheet_id": spreadsheet_id,
        "data_file_path": data_file_path,
        "focus_files": focus_files,
        "window_size": window_size,
        "step_size": step_size,
        "lens_id": DEFAULT_LENS_ID,
        "api_endpoint": DEFAULT_API_ENDPOINT,
        "max_run_time_sec": DEFAULT_MAX_RUN_SEC,
    }

# ---------- Session Handling ----------
def session_fn(session_id: str, session_endpoint: str, client: ArchetypeAI, args: dict) -> None:
    print(f"Session created: {session_id}")

    # Google Sheets init
    sheets = GoogleSheetsLogger(args["spreadsheet_id"])
    sheets.init_sheet()

    # Upload focus CSVs
    input_n_shot = {}
    for class_name, file_path in args["focus_files"].items():
        upload_response = client.files.local.upload(file_path)
        input_n_shot[class_name] = upload_response["file_id"]
        logging.info(f"Uploaded focus '{class_name}' -> {upload_response['file_id']}")

    # Upload data CSV
    data_upload_response = client.files.local.upload(args["data_file_path"])
    data_file_id = data_upload_response["file_id"]
    data_file_name = Path(args["data_file_path"]).name

    logging.info(f"Uploaded data file '{data_file_name}' -> {data_file_id}")

    # Configure lens & streams
    client.lens.sessions.process_event(session_id,
        build_session_modify_event(input_n_shot, args["window_size"], args["step_size"]))
    client.lens.sessions.process_event(session_id,
        build_input_event_csv(data_file_id, args["window_size"], args["step_size"]))
    client.lens.sessions.process_event(session_id, build_output_event())

    # SSE reader
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])

    print("\nProcessing… (Ctrl+C to stop)\n")
    window_count = 0
    try:
        for event in sse_reader.read(block=True):
            if isinstance(event, dict) and event.get("type") == "inference.result":
                result = event.get("event_data", {}).get("response")
                if result is not None:
                    window_count += 1
                    pred, conf, scores = sheets.parse_prediction_result(result)
                    print(f"Window {window_count}: {pred} ({conf}) — {scores}")
                    sheets.log_result(
                        file_name=data_file_name,
                        window_num=window_count,
                        predicted_result=result
                    )
    finally:
        sse_reader.close()
        logging.info(f"Completed analysis of {window_count} windows.")

# ---------- Main ----------
def main():
    if not os.path.exists("credentials.json") and not os.path.exists("token.pickle"):
        print("\n❌ Google credentials not found.")
        print("Please place your OAuth client file as 'credentials.json' in this directory.")
        print("The script will guide you through authorization on first run.\n")

    args = get_user_inputs()
    client = ArchetypeAI(args["api_key"], api_endpoint=args["api_endpoint"])

    print("\n--- Configuration Summary ---")
    print(f"Lens ID:      {args['lens_id']}")
    print(f"API Endpoint: {args['api_endpoint']}")
    print(f"Data file:    {args['data_file_path']}")
    print(f"Classes:      {len(args['focus_files'])}")
    for cls, p in args["focus_files"].items():
        print(f"  - {cls}: {p}")

    input("\nPress Enter to start…")

    client.lens.create_and_run_session(args["lens_id"], session_fn, auto_destroy=True, client=client, args=args)
    print("Session finished.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
