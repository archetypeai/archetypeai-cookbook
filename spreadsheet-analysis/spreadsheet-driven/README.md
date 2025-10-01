# Spreadsheet-Driven Machine State Analysis

Fully automated Google Sheets integration that reads config, data, and focus examples from sheets, then logs predictions back.

## Requirements

- Python 3.12
- [ArchetypeAI Python client](https://github.com/archetypeai/python-client)
- Google Sheets API credentials

Install dependencies:
```bash
pip install -r requirements.txt
```

## Setup

1. **Google Sheets API**:
   - Enable Sheets API in [Google Cloud Console](https://console.cloud.google.com)
   - Create OAuth 2.0 credentials
   - Download and save as `credentials.json` in this directory

2. **Create Template Spreadsheet**:
   ```bash
   python create_example_spreadsheet.py
   ```
   This creates a spreadsheet with:
   - **Config** sheet: API settings and parameters
   - **Data** sheet: CSV data to analyze
   - **Results** sheet: Prediction outputs
   - Focus class sheets (e.g., "healthy", "broken")

3. **Configure the Sheet**:
   - Fill in your API key in Config!B1
   - Add data to the Data sheet
   - Add example patterns to focus sheets
   - Set Config!B10 to "RUN" to trigger analysis

## Usage

```bash
python app.py
```

Enter your Google Sheets ID when prompted. The app will then:
- Monitor Config!B10 for "RUN" trigger
- Read configuration and data from sheets
- Process through Newton Lens
- Log results to Results sheet
- Update status in Config!B11

## Sheet Structure

### Config Sheet
| Field | Value |
|-------|-------|
| API Key | your-api-key |
| Lens ID | lns-1d519091822706e2... |
| API Endpoint | https://api.archetypeai.dev/v0.5 |
| Window Size | 1024 |
| Step Size | 1024 |
| Trigger | RUN (to start) |
| Status | (auto-updated) |

### Data Sheet
CSV format with timestamp and data columns:
```
timestamp,a1,a2,a3,a4
2024-01-01 00:00:00,1.23,4.56,7.89,0.12
```

### Focus Sheets
Create separate sheets for each class (e.g., "healthy", "broken") with example patterns.

### Results Sheet
Auto-populated with:
- Timestamp
- Window number
- Predicted class
- Confidence %
- All scores

## Example Workflow

1. Run `create_example_spreadsheet.py` to generate template
2. Fill in your API key and data
3. Start monitoring: `python app.py`
4. Set trigger cell to "RUN" in spreadsheet
5. Watch results populate automatically