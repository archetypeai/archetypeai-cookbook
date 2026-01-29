"""
Activity Monitor Quickstart
Activity monitoring using Newton's Activity Monitor Lens for video or RTSP analysis
Supports both YAML configuration files and interactive CLI mode
"""

import argparse
import logging
import os
import signal
import sys
from pathlib import Path
import yaml
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

# ---------- YAML Configuration ----------
def load_config(config_path: str) -> dict:
    """Load and validate YAML configuration file."""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            print(f"❌ Configuration file not found: {config_path}")
            print(f"💡 Copy config.example.yaml to config.yaml and update with your values")
            sys.exit(1)
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate required fields
        required_fields = [
            ('api', 'key'),
            ('input', 'type'),
            ('input', 'source'),
            ('monitor', 'focus')
        ]
        
        for section, field in required_fields:
            if section not in config or field not in config[section]:
                print(f"❌ Missing required field: {section}.{field}")
                sys.exit(1)
        
        # Validate input type
        if config['input']['type'] not in ('video', 'rtsp'):
            print(f"❌ Invalid input.type: {config['input']['type']}. Must be 'video' or 'rtsp'")
            sys.exit(1)
        
        # Set defaults
        if 'step_size' not in config.get('monitor', {}):
            config['monitor']['step_size'] = DEFAULT_STEP_SIZE
        
        if 'temporal_focus' not in config.get('monitor', {}):
            config['monitor']['temporal_focus'] = DEFAULT_TEMPORAL_FOCUS
        
        if 'output' not in config:
            config['output'] = {'format': 'text', 'log_file': None}
        
        return config
        
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML configuration: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        sys.exit(1)


def print_config_summary(config: dict):
    """Print a summary of the loaded configuration."""
    print("\n--- Configuration Summary ---")
    print(f"Input:  {config['input']['type'].upper()}")
    
    if config['input']['type'] == 'video':
        print(f"Video:  {config['input']['source']}")
    else:
        print(f"RTSP:   {config['input']['source']}")
    
    print(f"Focus:  {config['monitor']['focus']}")
    print(f"Step size: {config['monitor']['step_size']} frames")
    
    if config['output'].get('log_file'):
        print(f"Logging to: {config['output']['log_file']}")
    
    print("----------------------------\n")


def config_to_args(config: dict) -> dict:
    """Convert YAML config to args format expected by session_callback."""
    input_type = config['input']['type']
    
    args = {
        "api_key": config['api']['key'],
        "input_type": input_type,
        "video_file_path": config['input']['source'] if input_type == 'video' else None,
        "rtsp_url": config['input']['source'] if input_type == 'rtsp' else None,
        "focus": config['monitor']['focus'],
        "instruction": DEFAULT_INSTRUCTION,
        "max_run_time_sec": DEFAULT_MAX_RUN_SEC,
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
        "step_size": config['monitor']['step_size'],
        "temporal_focus": config['monitor']['temporal_focus'],
        "api_endpoint": config['api'].get('endpoint', ArchetypeAI.get_default_endpoint()),
    }
    
    # Validate video file exists if using video input
    if input_type == 'video' and not os.path.exists(args['video_file_path']):
        print(f"❌ Video file not found: {args['video_file_path']}")
        sys.exit(1)
    
    return args


# ---------- Interactive inputs (Legacy) ----------
def get_user_inputs() -> dict:
    print(colorize_text(BANNER))
    print("\n=== Activity Monitor (Interactive Mode) ===\n")

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
        # Close any active reader
        sse_reader.close()


def main():
    """Main entry point for Activity Monitor."""
    parser = argparse.ArgumentParser(
        description='Activity Monitor - Analyze video content with natural language queries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default config file
  python quickstart.py
  
  # Use custom config file
  python quickstart.py --config my_config.yaml
  
  # Run in interactive mode (legacy)
  python quickstart.py --interactive
        """
    )
    
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to YAML configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive CLI mode (legacy)'
    )
    
    args_parsed = parser.parse_args()
    
    print(colorize_text(BANNER))
    print("\n=== Activity Monitor ===\n")
    
    if args_parsed.interactive:
        # Legacy interactive mode
        args = get_user_inputs()
    else:
        # YAML configuration mode
        config = load_config(args_parsed.config)
        print(f"✓ Configuration loaded from: {args_parsed.config}")
        print_config_summary(config)
        args = config_to_args(config)
    
    # Initialize client
    client = ArchetypeAI(api_key=args["api_key"], endpoint=args["api_endpoint"])

    # Print summary
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
