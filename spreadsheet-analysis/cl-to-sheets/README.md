# Machine State → Google Sheets

Analyze CSV time-series data and log predictions directly to Google Sheets.

## Requirements

- Python 3.9+
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
   - First run will open browser for authorization

2. **Get Sheets ID**:
   - From your sheet URL: `https://docs.google.com/spreadsheets/d/SHEETS_ID/edit`
   - Copy the `SHEETS_ID` portion

## Usage

```bash
python app.py
```

## Interactive Prompts

1. **API Key**: Your ArchetypeAI API key
2. **Sheets ID**: Your Google Sheets document ID
3. **Data CSV**: Path to the CSV file to analyze
4. **Focus Files**: Example CSV files for each class
   - File name becomes the class name
   - Add multiple examples, type 'done' when finished
5. **Window/Step Size**: Analysis parameters (defaults: 1024)

## Example Session

```
=== Machine State → Google Sheets ===

Enter your ArchetypeAI API key: your-api-key
Enter your Google Sheets ID: 1abc123def456...
Enter path to CSV to analyze: data/sensor_readings.csv

--- Add Focus Files ---
Focus CSV path (or 'done'): samples/normal.csv
 Added: class 'normal' from normal.csv
Focus CSV path (or 'done'): samples/fault.csv
 Added: class 'fault' from fault.csv
Focus CSV path (or 'done'): done

Processing… (Ctrl+C to stop)

Window 1: normal (95.2%) — normal: 95.2, fault: 4.8
Window 2: normal (88.1%) — normal: 88.1, fault: 11.9
Window 3: fault (73.5%) — fault: 73.5, normal: 26.5
```

## Output

Results are automatically logged to your Google Sheet with:
- Timestamp
- File analyzed
- Window number
- Predicted class
- Confidence percentage
- All class scores
- Status and notes