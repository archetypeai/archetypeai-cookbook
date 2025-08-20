#!/usr/bin/env python3
"""
Spreadsheet → Newton Lens → Results (Google Sheets)
Reads config and data from a Google Sheet, streams CSV to a Newton Lens using
focus-class sheets as n-shot examples, and logs predictions back to the sheet.
Monitors a trigger cell to run on demand.
"""

import logging
import os
import sys
import time
import csv
import tempfile
import pickle
from datetime import datetime
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

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

# ---------- Defaults ----------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TRIGGER_CELL = "Config!B10"
STATUS_CELL  = "Config!B11"
CONFIG_RANGE = "Config!A:B"
DATA_SHEET   = "Data"
RESULTS_HDR_RANGE = "Results!A1:E1"
RESULTS_RANGE     = "Results!A:E"

# ---------- Event builders ----------
def build_session_modify_event(input_n_shot: dict, cfg: dict) -> dict:
    return {
        "type": "session.modify",
        "event_data": {
            "input_n_shot": input_n_shot,
            "csv_configs": {
                "timestamp_column": cfg.get("timestamp_column", "timestamp"),
                "data_columns": cfg.get("data_columns", "a1,a2,a3,a4").split(","),
                "window_size": int(cfg.get("window_size", 1024)),
                "step_size": int(cfg.get("step_size", 1024)),
            }
        }
    }

def build_input_event_csv(file_id: str, cfg: dict) -> dict:
    return {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "csv_file_reader",
            "stream_config": {
                "file_id": file_id,
                "window_size": int(cfg.get("window_size", 1024)),
                "step_size": int(cfg.get("step_size", 1024)),
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

# ---------- Sheets Runner ----------
class SpreadsheetLensRunner:
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

    # ---- Sheet helpers
    def read_config(self) -> dict | None:
        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=CONFIG_RANGE
            ).execute()
            cfg = {}
            for row in res.get("values", []):
                if len(row) >= 2 and row[0] and row[1]:
                    cfg[row[0].strip().lower().replace(" ", "_")] = row[1].strip()
            for req in ("api_key", "lens_id", "api_endpoint"):
                if req not in cfg:
                    raise ValueError(f"Missing required config: {req}")
            return cfg
        except Exception as e:
            logging.error(f"Error reading config: {e}")
            return None

    def get_trigger(self) -> bool:
        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=TRIGGER_CELL
            ).execute()
            vals = res.get("values", [])
            return bool(vals and vals[0] and vals[0][0].strip().upper() == "RUN")
        except Exception as e:
            logging.error(f"Error checking trigger: {e}")
            return False

    def clear_trigger(self) -> None:
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=TRIGGER_CELL,
                valueInputOption="USER_ENTERED", body={"values": [[""]]}
            ).execute()
        except Exception as e:
            logging.error(f"Error clearing trigger: {e}")

    def set_status(self, status: str, details: str = "") -> None:
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text = f"{status} — {ts}" + (f" — {details}" if details else "")
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=STATUS_CELL,
                valueInputOption="USER_ENTERED", body={"values": [[text]]}
            ).execute()
        except Exception as e:
            logging.error(f"Error updating status: {e}")

    def read_sheet(self, sheet_name: str) -> list[list[str]] | None:
        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=f"{sheet_name}!A:Z"
            ).execute()
            return res.get("values", []) or None
        except Exception as e:
            logging.error(f"Error reading sheet {sheet_name}: {e}")
            return None

    def write_results_header_if_missing(self) -> None:
        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=RESULTS_HDR_RANGE
            ).execute()
            if not res.get("values"):
                hdr = [["Timestamp", "Window", "Predicted Class", "Confidence %", "All Scores"]]
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id, range=RESULTS_HDR_RANGE,
                    valueInputOption="USER_ENTERED", body={"values": hdr}
                ).execute()
                logging.info("Initialized Results sheet header.")
        except Exception as e:
            logging.error(f"Error initializing Results header: {e}")

    def append_result(self, window_num: int, predicted_result) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pred, conf, scores = self.parse_prediction_result(predicted_result)
        row = [[ts, f"Window {window_num}", pred, conf, scores]]
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id, range=RESULTS_RANGE,
                valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
                body={"values": row}
            ).execute()
        except Exception as e:
            logging.error(f"Error appending result: {e}")

    def parse_prediction_result(self, result):
        try:
            if isinstance(result, list) and len(result) >= 2 and isinstance(result[1], dict):
                predicted = str(result[0])
                scores = result[1]
                conf = scores.get(predicted, 0.0)
                all_scores = ", ".join(f"{k}: {v:.1f}" for k, v in scores.items())
                return predicted, f"{conf:.1f}%", all_scores
            return str(result), "N/A", str(result)
        except Exception as e:
            logging.error(f"Error parsing result {result}: {e}")
            return str(result), "N/A", str(result)

    # ---- CSV temp helpers
    def to_temp_csv(self, rows: list[list[str]]) -> str | None:
        """Write rows to a temp CSV file and return its path."""
        try:
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
            with f as fp:
                writer = csv.writer(fp)
                writer.writerows(rows)
            return f.name
        except Exception as e:
            logging.error(f"Error writing temp CSV: {e}")
            return None

    def list_focus_sheets(self) -> list[str]:
        """List candidate focus-class sheets (excludes known operational tabs)."""
        try:
            meta = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            excluded = {"config", "data", "results", "sheet1"}
            out = []
            for s in meta.get("sheets", []):
                title = s["properties"]["title"]
                if title.lower() not in excluded:
                    out.append(title)
            return out
        except Exception as e:
            logging.error(f"Error listing focus sheets: {e}")
            return []

# ---------- One-shot run (reads config, builds temps, runs Lens, logs results) ----------
def run_once(runner: SpreadsheetLensRunner):
    cfg = runner.read_config()
    if not cfg:
        runner.set_status("ERROR", "Config read failed")
        return

    runner.set_status("STARTING", "Reading sheets")
    data_values = runner.read_sheet(DATA_SHEET)
    if not data_values:
        runner.set_status("ERROR", "No data in Data sheet")
        return

    focus_tabs = runner.list_focus_sheets()
    if not focus_tabs:
        runner.set_status("ERROR", "No focus sheets found")
        return

    # Build temp CSV files
    temp_paths: list[str] = []
    try:
        data_csv = runner.to_temp_csv(data_values)
        if not data_csv:
            runner.set_status("ERROR", "Could not create data CSV")
            return
        temp_paths.append(data_csv)

        focus_files: dict[str, str] = {}
        for tab in focus_tabs:
            rows = runner.read_sheet(tab)
            if rows:
                p = runner.to_temp_csv(rows)
                if p:
                    focus_files[tab.lower()] = p
                    temp_paths.append(p)

        if not focus_files:
            runner.set_status("ERROR", "No valid focus CSVs")
            return

        runner.write_results_header_if_missing()
        runner.set_status("RUNNING", f"{len(focus_files)} classes")

        # ---- Lens: create client and run session via callback
        client = ArchetypeAI(cfg["api_key"], api_endpoint=cfg["api_endpoint"])

        def session_fn(session_id: str, session_endpoint: str, client: ArchetypeAI, args: dict):
            # Upload focus CSVs
            input_n_shot = {}
            for cls, path in focus_files.items():
                r = client.files.local.upload(path)
                input_n_shot[cls] = r["file_id"]
                logging.info(f"Uploaded focus '{cls}' -> {r['file_id']}")

            # Upload data CSV
            r = client.files.local.upload(data_csv)
            data_file_id = r["file_id"]

            # Configure lens & streams
            client.lens.sessions.process_event(session_id, build_session_modify_event(input_n_shot, cfg))
            client.lens.sessions.process_event(session_id, build_input_event_csv(data_file_id, cfg))
            client.lens.sessions.process_event(session_id, build_output_event())

            # SSE reader
            sse = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=int(cfg.get("max_run_time_sec", 600)))
            window_count = 0
            for ev in sse_reader_iter(sse):
                if isinstance(ev, dict) and ev.get("type") == "inference.result":
                    result = ev.get("event_data", {}).get("response")
                    if result is not None:
                        window_count += 1
                        pred, conf, _ = runner.parse_prediction_result(result)
                        logging.info(f"Window {window_count}: {pred} ({conf})")
                        runner.append_result(window_count, result)
                        if window_count % 10 == 0:
                            runner.set_status("RUNNING", f"Processed {window_count} windows")
            sse.close()
            runner.set_status("COMPLETED", f"Analyzed {window_count} windows")

        # Kick off session
        client.lens.create_and_run_session(cfg["lens_id"], session_fn, auto_destroy=True, client=client, args={})

    except Exception as e:
        logging.error(f"Run error: {e}")
        runner.set_status("ERROR", str(e))
    finally:
        # Cleanup temps
        for p in temp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass

def sse_reader_iter(sse_reader):
    """Helper to ensure we always close SSE properly if exceptions occur."""
    try:
        for ev in sse_reader.read(block=True):
            yield ev
    finally:
        try:
            sse_reader.close()
        except Exception:
            pass

# ---------- Main: monitor trigger cell ----------
def main():
    if not os.path.exists("credentials.json") and not os.path.exists("token.pickle"):
        print("\nℹ️ Google credentials not found yet.")
        print("Place your OAuth client file as 'credentials.json' in this directory.")
        print("You will be guided through authorization on first run.\n")

    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip() or input("Enter your Google Sheets ID: ").strip()
    if not spreadsheet_id:
        print("Google Sheets ID is required."); sys.exit(1)

    runner = SpreadsheetLensRunner(spreadsheet_id)

    print("\n🔄 Monitoring for triggers…")
    print(f"- Put 'RUN' in {TRIGGER_CELL} to start an analysis")
    print(f"- Status updates will appear in {STATUS_CELL}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            if runner.get_trigger():
                logging.info("Trigger detected — starting analysis…")
                runner.clear_trigger()
                runner.set_status("TRIGGERED", "Starting")
                run_once(runner)
                logging.info("Analysis complete. Waiting for next trigger…")
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped.")
        runner.set_status("STOPPED", "Monitoring ended")

if __name__ == "__main__":
    main()
