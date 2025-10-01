# Machine State Quickstart

Interactive CSV time-series classification using one-shot learning.

## Requirements

- Python 3.12
- [ArchetypeAI Python client](https://github.com/archetypeai/python-client)

You can install the ArchetypeAI client by following the instructions in the repository linked above.

## Usage

```bash
python quickstart.py
```

## What it does

Analyzes CSV time-series data and classifies it based on example patterns you provide.

## Interactive Prompts

1. **API Key**: Your ArchetypeAI API key
2. **Data CSV**: Path to the CSV file you want to analyze
3. **Focus Files**: Example CSV files for each class (e.g., `healthy.csv`, `broken.csv`)
   - File name becomes the class name
   - Add multiple examples, type 'done' when finished
4. **Window Size**: Data points per analysis window (default: 1024)
5. **Step Size**: Points to advance between windows (default: 1024)

## Example Session

```
=== Machine State Lens ===

Enter your API key: your-key-here
Enter path to CSV to analyze: sample-files/data.csv

--- Add Focus Files ---
Provide CSV example(s) for each class (e.g., healthy.csv -> class 'healthy').
Type 'done' when finished.

Focus CSV path (or 'done'): sample-files/focus/healthy.csv
 Added: class 'healthy' from healthy.csv
Focus CSV path (or 'done'): sample-files/focus/broken.csv
 Added: class 'broken' from broken.csv
Focus CSV path (or 'done'): done

Window size [default 1024]: 
Step size   [default 1024]: 

--- Configuration Summary ---
Lens ID:      lns-1d519091822706e2-bc108andqxf8b4os
API Endpoint: https://api.archetypeai.dev/v0.5
Data file:    sample-files/data.csv
Classes:      2
  - healthy: sample-files/focus/healthy.csv
  - broken: sample-files/focus/broken.csv

Press Enter to start the analysis...

Streaming… Press Ctrl+C to stop.

[2024-01-15T10:30:45.123] → Predicted class: healthy
[2024-01-15T10:31:15.456] → Predicted class: healthy
[2024-01-15T10:31:45.789] → Predicted class: broken
[2024-01-15T10:32:16.012] → Predicted class: broken
```

## Output

The system outputs real-time predictions showing which class best matches each window of your data. Each prediction includes a timestamp and the predicted class name.