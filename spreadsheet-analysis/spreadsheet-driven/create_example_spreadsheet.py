"""
Script to create an example Google Spreadsheet with the correct structure
for the app.py
"""

import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def authenticate():
    """Authenticate with Google Sheets API"""
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('sheets', 'v4', credentials=creds)


def create_example_spreadsheet():
    """Create an example spreadsheet with the correct structure"""
    
    if not os.path.exists('credentials.json'):
        print("❌ ERROR: credentials.json not found!")
        print("Please follow the setup instructions to get Google API credentials.")
        return
    
    service = authenticate()
    
    # Create new spreadsheet
    spreadsheet = {
        'properties': {
            'title': 'Machine State Lens - Example Setup'
        }
    }
    
    spreadsheet = service.spreadsheets().create(body=spreadsheet).execute()
    spreadsheet_id = spreadsheet['spreadsheetId']
    
    print(f"✅ Created spreadsheet: {spreadsheet['properties']['title']}")
    print(f"📋 Spreadsheet ID: {spreadsheet_id}")
    print(f"🔗 URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    
    # Rename Sheet1 to Config and add other sheets
    requests = []
    
    # Rename Sheet1 to Config
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': 0,
                'title': 'Config'
            },
            'fields': 'title'
        }
    })
    
    # Add other sheets
    sheet_names = ['Data', 'healthy', 'broken', 'Results']
    for sheet_name in sheet_names:
        requests.append({
            'addSheet': {
                'properties': {
                    'title': sheet_name
                }
            }
        })
    
    # Execute batch update
    body = {'requests': requests}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    
    # Add Config data
    config_data = [
        ['API Key', 'your-api-key-here'],
        ['Lens ID', 'lns-1d519091822706e2-bc108andqxf8b4os'],
        ['API Endpoint', 'https://api.archetypeai.dev/v0.5'],
        ['Timestamp Column', 'timestamp'],
        ['Data Columns', 'a1,a2,a3,a4'],
        ['Window Size', '1024'],
        ['Step Size', '1024'],
        ['', ''],
        ['', ''],
        ['RUN TRIGGER', '(enter RUN here to start)'],
        ['STATUS', 'Ready']
    ]
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range='Config!A1:B11',
        valueInputOption='USER_ENTERED',
        body={'values': config_data}
    ).execute()
    
    # Add sample data headers
    data_headers = [['timestamp', 'a1', 'a2', 'a3', 'a4']]
    
    for sheet in ['Data', 'healthy', 'broken']:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet}!A1:E1',
            valueInputOption='USER_ENTERED',
            body={'values': data_headers}
        ).execute()
    
    # Add sample data to sheets
    sample_data = [
        ['2024-01-01 10:00:00', '1.23', '4.56', '7.89', '0.12'],
        ['2024-01-01 10:00:01', '2.34', '5.67', '8.90', '1.23'],
        ['2024-01-01 10:00:02', '3.45', '6.78', '9.01', '2.34']
    ]
    
    for sheet in ['Data', 'healthy', 'broken']:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet}!A2:E4',
            valueInputOption='USER_ENTERED',
            body={'values': sample_data}
        ).execute()
    
    print("\n✅ Example spreadsheet created successfully!")
    print("\n📝 Next steps:")
    print("1. Replace 'your-api-key-here' with your actual API key")
    print("2. Import your actual CSV data into the Data, healthy, and broken sheets")
    print("3. Run: python app.py")
    print("4. Enter 'RUN' in cell B10 to trigger analysis")
    
    return spreadsheet_id


if __name__ == "__main__":
    create_example_spreadsheet()