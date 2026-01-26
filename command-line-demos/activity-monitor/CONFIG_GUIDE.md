# Activity Monitor Configuration Guide

## Quick Start

1. Copy the example configuration:
```bash
   cp config.example.yaml config.yaml
```

2. Edit `config.yaml` with your API key and preferences

3. Run the monitor:
```bash
   python quickstart.py
```

## Configuration Options

### API Settings
- `api.key`: Your ArchetypeAI API key (required)

### Input Configuration
- `input.type`: Either `video` or `rtsp` (required)
- `input.source`: Path to video file or RTSP URL (required)

### Monitor Settings
- `monitor.focus`: Your query about the video (required)
- `monitor.step_size`: Frames between analysis (optional, default: 60)

### Output Settings
- `output.format`: `text` or `json` (optional, default: text)
- `output.log_file`: Path to save results (optional)

## Examples

See the `examples/` directory for sample configurations.

## Legacy Interactive Mode

To use the original interactive CLI:
```bash
python quickstart.py --interactive
```
