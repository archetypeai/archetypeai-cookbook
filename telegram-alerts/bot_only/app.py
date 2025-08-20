"""
Telegram Activity Monitor Bot
Control Newton’s Activity Monitor Lens to send alerts via Telegram commands.
Streams RTSP or video files, detects alerts, and pushes notifications to Telegram.
"""

import logging
import os
import requests
import threading
from pprint import pformat
from archetypeai.api_client import ArchetypeAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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

def send_telegram_alert(message: str):
    """Send a simple Telegram text alert."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        logging.info("✅ Telegram alert sent!")
    except Exception as e:
        logging.error(f"❌ Failed to send Telegram alert: {e}")

send_telegram_alert("Bot started. Send /start to see commands.")

# ---------- Globals ----------
last_alert_state = False
monitoring_thread = None
stop_flag = False
current_client = None
current_session_id = None
last_args = {}

# ---------- Session Handling ----------
def session_fn(session_id, session_endpoint, client, args):
    global last_alert_state, stop_flag

    # --- Input stream
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
                    "window_size": 1
                }
            }
        }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Stream response:\n{pformat(response, indent=4)}")

    # --- Focus & instruction
    event = {
        "type": "session.modify",
        "event_data": {
            "focus": args["focus"],
            "max_new_tokens": 256,
            "instruction": args["instruction"]
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Instruction response:\n{pformat(response, indent=4)}")

    # --- Output stream
    event = {
        "type": "output_stream.set",
        "event_data": {"stream_type": "server_side_events_writer", "stream_config": {}}
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"Output stream response:\n{pformat(response, indent=4)}")

    # --- SSE Reader
    sse_reader = client.lens.sessions.create_sse_consumer(session_id, max_read_time_sec=args["max_run_time_sec"])
    for event in sse_reader.read(block=True):
        if stop_flag:
            logging.info("🛑 Monitoring stopped.")
            break

        logging.info(event)

        # --- Alert detection
        if isinstance(event, dict) and event.get("type") == "inference.result":
            resp = event.get("event_data", {}).get("response", [])
            if resp:
                text = resp[0]
                is_alert = "alert:" in text.lower()

                if is_alert and not last_alert_state:
                    alert_text = text.split("Alert:", 1)[-1].strip()
                    logging.info(f"🚨 Alert detected: {alert_text}")
                    send_telegram_alert(f"Alert: {alert_text}")

                last_alert_state = is_alert

    sse_reader.close()

# ---------- Monitoring Control ----------
def start_monitoring(api_key, input_type, rtsp_url, video_file_id, focus):
    """Start a new monitoring session."""
    global stop_flag, current_client, current_session_id, last_args
    stop_flag = False

    args = {
        "api_key": api_key,
        "rtsp_url": rtsp_url,
        "video_file_id": video_file_id,
        "input_type": input_type,
        "focus": focus,
        "instruction": DEFAULT_INSTRUCTION,
        "max_run_time_sec": 600.0
    }
    last_args = args.copy()

    client = ArchetypeAI(api_key, api_endpoint=ArchetypeAI.get_default_endpoint())
    current_client = client
    send_telegram_alert(f"Monitoring started with focus: {focus}")

    def wrapper(session_id, session_endpoint, client, args):
        global current_session_id
        current_session_id = session_id
        session_fn(session_id, session_endpoint, client, args)

    client.lens.create_and_run_session(LENS_ID, wrapper, auto_destroy=True, client=client, args=args)

def stop_monitoring():
    """Stop and destroy the current session properly."""
    global stop_flag, current_client, current_session_id
    stop_flag = True
    if current_client and current_session_id:
        try:
            current_client.lens.sessions.destroy(current_session_id)
            logging.info(f"Session {current_session_id} destroyed.")
        except Exception as e:
            logging.error(f"Failed to destroy session: {e}")
    else:
        logging.info("⚠️ No active session to stop.")

def restart_with_new_focus(new_focus):
    """Restart monitoring with updated focus."""
    global monitoring_thread, last_args, stop_flag
    if not monitoring_thread or not monitoring_thread.is_alive():
        raise RuntimeError("No active session to restart.")

    logging.info(f"Restarting with new focus: {new_focus}")
    stop_monitoring()
    monitoring_thread.join()

    last_args["focus"] = new_focus
    stop_flag = False

    monitoring_thread = threading.Thread(
        target=start_monitoring,
        args=(last_args["api_key"], last_args["input_type"], last_args["rtsp_url"], last_args["video_file_id"], last_args["focus"]),
        daemon=True
    )
    monitoring_thread.start()

# ---------- Telegram Commands ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start_monitoring <api_key> <rtsp|video> <url_or_id> <focus>\n"
        "/stop_monitoring\n"
        "/change_focus <new focus>\n"
        "/status"
    )

async def start_monitoring_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitoring_thread
    if monitoring_thread and monitoring_thread.is_alive():
        await update.message.reply_text("⚠️ Already running. Use /stop_monitoring first.")
        return

    if len(context.args) < 4:
        await update.message.reply_text("Usage: /start_monitoring <api_key> <rtsp|video> <url_or_id> <focus>")
        return

    api_key, input_type, url_or_id, *focus_words = context.args
    focus = " ".join(focus_words)
    rtsp_url, video_file_id = (url_or_id, None) if input_type == "rtsp" else (None, url_or_id)

    monitoring_thread = threading.Thread(
        target=start_monitoring,
        args=(api_key, input_type, rtsp_url, video_file_id, focus),
        daemon=True
    )
    monitoring_thread.start()

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_monitoring()
    await update.message.reply_text("🛑 Monitoring stopped.")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    running = monitoring_thread and monitoring_thread.is_alive()
    await update.message.reply_text("✅ Running." if running else "❌ Not running.")

async def change_focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /change_focus <new_focus>")
        return
    new_focus = " ".join(context.args)
    try:
        restart_with_new_focus(new_focus)
        await update.message.reply_text(f"🔄 Focus updated: {new_focus}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to change focus: {e}")

# ---------- Main ----------
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("start_monitoring", start_monitoring_cmd))
    app.add_handler(CommandHandler("stop_monitoring", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("change_focus", change_focus_cmd))

    print("🤖 Telegram bot is running...")
    app.run_polling()
