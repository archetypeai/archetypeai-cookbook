# Activity Monitor Configuration Guide

## Quick Start

1. **Get your API key** from [Archetype AI](https://archetypeai.app)

2. **Install dependencies**:
```bash
   pip install -r requirements.txt
```

3. **Copy the example configuration**:
```bash
   cp config.example.yaml config.yaml
```

4. **Edit `config.yaml`** with your API key and preferences:
```bash
   nano config.yaml  # or use any text editor
```

5. **Run the monitor**:
```bash
   python quickstart.py
```

## Configuration Options

### API Settings
- `api.key`: Your ArchetypeAI API key (required) - Get it from https://archetypeai.app

### Input Configuration
- `input.type`: Either `video` or `rtsp` (required)
- `input.source`: Path to video file or RTSP URL (required)

### Monitor Settings
- `monitor.focus`: Your query about the video (required)
- `monitor.step_size`: Frames between analysis (optional, default: 60)
  - **30 frames**: More detail, slower processing
  - **60 frames**: Balanced (recommended)
  - **90-120 frames**: Faster, broader patterns

### Output Settings
- `output.format`: `text` or `json` (optional, default: text)
- `output.log_file`: Path to save results (optional)

## Example Usage

### Analyze a Local Video
```yaml
api:
  key: "your-api-key"

input:
  type: "video"
  source: "./sample-videos/delivery.mp4"

monitor:
  focus: "Is there a person making a delivery?"
  step_size: 60

output:
  format: "text"
```

Run with:
```bash
python quickstart.py --config config.yaml
```

### Monitor RTSP Stream
```yaml
api:
  key: "your-api-key"

input:
  type: "rtsp"
  source: "rtsp://192.168.1.100:554/stream"

monitor:
  focus: "Detect when a person enters"
  step_size: 30

output:
  format: "json"
  log_file: "monitor.log"
```

## Examples

See the `examples/` directory for more sample configurations:
- `examples/video_analysis.yaml` - Local video file analysis
- `examples/rtsp_monitoring.yaml` - Real-time RTSP stream monitoring

## Legacy Interactive Mode

To use the original interactive CLI:
```bash
python quickstart.py --interactive
```

## Troubleshooting

### Configuration file not found
```
❌ Configuration file not found: config.yaml
```
**Solution**: Copy `config.example.yaml` to `config.yaml`

### Missing required field
```
❌ Missing required field: api.key
```
**Solution**: Ensure all required fields are filled in your config file

### Video file not found
```
❌ Video file not found: ./path/to/video.mp4
```
**Solution**: Check the video path in your config. Sample videos are in `./sample-videos/`

### Module not found
```
ModuleNotFoundError: No module named 'yaml'
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

## Getting Help

- [Archetype AI Documentation](https://docs.archetypeai.app)
- [Python Client Library](https://docs.archetypeai.app/libraries/python)
- [API Reference](https://docs.archetypeai.app/api-reference)
