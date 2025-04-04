import os
import gspread
from google.oauth2.service_account import Credentials
import random
from datetime import datetime, timedelta
import string
import time

# Define the scope and authenticate with Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
# Path to your service account credentials JSON file
CREDENTIALS_FILE = "myproject-23c78-40861029cd7b.json"

# The spreadsheet ID and worksheet name where records are stored.
SPREADSHEET_ID = '1emelv_ISXeKylC04rlO6givV96bpVsj-4cyE0ek3sLs'
WORKSHEET_NAME = 'SATS'

# Authenticate and initialize Google Sheets API
def authenticate_google_sheets():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # Get the spreadsheet
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    # Try to get the worksheet, create it if it doesn't exist
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        # Check if we need to update the headers for existing worksheet
        headers = worksheet.row_values(1)
        # If we need to update headers or we're setting up the first time
        if "Checker ID" not in headers or "Team Name" not in headers or "Timestamp Breakdown (CPCS)" not in headers or "BT Number" not in headers or "Timestamp Handover" not in headers or "Trolley Staff ID" not in headers:
            print("Updating headers to add missing columns")
            
            # First clear the existing content of the first two rows to avoid conflicts
            worksheet.batch_clear(["A1:Q2"])
            
            # Add the category headers in row 1
            title_row = ["AWB Information", "", "", "", "", "", "", "", "", "Towing", "", "", "Breakdown", "", "", "", ""]
            worksheet.update('A1:Q1', [title_row])
            
            # Merge cells for category headers
            worksheet.merge_cells('A1:I1')  # AWB Information
            worksheet.merge_cells('J1:L1')  # Towing
            worksheet.merge_cells('M1:Q1')  # Breakdown
            
            # Format the header row
            worksheet.format('A1:Q1', {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": True, "fontSize": 12}
            })
            
            # Add the column headers in row 2
            headers = [
                "Flight #", "Scheduled Arrival Time", "Actual Arrival Time", 
                "MAWB", "Flight Origin", "Flight Destination", 
                "No. of Pcs (AWB)", "Gross Weight", "Commodity Type", 
                "BT Number", "Timestamp Handover", "Trolley Staff ID",
                "No. of Pcs (Received)", "Discrepancy", "Checker ID", "Team Name", 
                "Timestamp Breakdown (CPCS)"
            ]
            worksheet.update('A2:Q2', [headers])
            
            # Format the column headers
            worksheet.format('A2:Q2', {
                "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                "textFormat": {"bold": True}
            })
    
    except gspread.exceptions.WorksheetNotFound:
        # Create the worksheet with appropriate headers
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=17)
        
        # Add the category headers in row 1
        title_row = ["AWB Information", "", "", "", "", "", "", "", "", "Towing", "", "", "Breakdown", "", "", "", ""]
        worksheet.update('A1:Q1', [title_row])
        
        # Merge cells for category headers
        worksheet.merge_cells('A1:I1')  # AWB Information
        worksheet.merge_cells('J1:L1')  # Towing
        worksheet.merge_cells('M1:Q1')  # Breakdown
        
        # Format the header row
        worksheet.format('A1:Q1', {
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "horizontalAlignment": "CENTER",
            "textFormat": {"bold": True, "fontSize": 12}
        })
        
        # Add the column headers in row 2
        headers = [
            "Flight #", "Scheduled Arrival Time", "Actual Arrival Time", 
            "MAWB", "Flight Origin", "Flight Destination", 
            "No. of Pcs (AWB)", "Gross Weight", "Commodity Type", 
            "BT Number", "Timestamp Handover", "Trolley Staff ID",
            "No. of Pcs (Received)", "Discrepancy", "Checker ID", "Team Name", 
            "Timestamp Breakdown (CPCS)"
        ]
        worksheet.append_row(headers)
        
        # Format the column headers
        worksheet.format('A2:Q2', {
            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
            "textFormat": {"bold": True}
        })
        
        print(f"Created new worksheet: {WORKSHEET_NAME}")
    
    return worksheet

def check_discrepancy(pcs_awb, pcs_received):
    """Returns 'Yes' if there's a discrepancy, otherwise 'No'."""
    return "Yes" if pcs_awb is not None and pcs_received is not None and pcs_awb != pcs_received else "No"

def update_google_sheet(record, checker_id=None, team_name=None, bt_number=None, timestamp_start=None, trolley_staff_id=None):
    """
    Updates the Google Sheet with the latest FlightRecord data.
    If the record (identified by its MAWB) exists, update its row.
    Otherwise, append a new row.
    """
    # Get worksheet (authenticate if needed)
    try:
        worksheet = authenticate_google_sheets()
    except Exception as e:
        print(f"Error authenticating with Google Sheets: {e}")
        return
    
    # Determine discrepancy
    discrepancy = check_discrepancy(record.pcs_awb, record.pcs_received)
    record.discrepancy = (discrepancy == "Yes")
    record.save()
    
    # Add current timestamp for completion
    current_timestamp = datetime.now().isoformat()
    
    # Get all records from the sheet
    try:
        # Skip the first 2 rows (title and header rows)
        records = worksheet.get_all_records(head=2)
    except Exception as e:
        print("Error fetching records from Google Sheet:", e)
        records = []
    
    # Find the existing record in the sheet to preserve data
    existing_record = next((r for r in records if r.get("MAWB") == record.mawb), None)
    
    # If we're updating only piece count (breakdown) information, 
    # preserve existing towing data
    if existing_record and not bt_number and not timestamp_start and not trolley_staff_id:
        bt_number = existing_record.get("BT Number", "")
        timestamp_start = existing_record.get("Timestamp Handover", "")
        trolley_staff_id = existing_record.get("Trolley Staff ID", "")
        print(f"Preserving existing towing data: BT={bt_number}, Staff={trolley_staff_id}")
    
    # Similarly, if we're only updating towing info, preserve breakdown data
    if existing_record and not checker_id and not team_name:
        if not record.pcs_received and existing_record.get("No. of Pcs (Received)"):
            try:
                record.pcs_received = int(existing_record.get("No. of Pcs (Received)"))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse received pieces: {existing_record.get('No. of Pcs (Received)')}")
        
        if not checker_id:
            checker_id = existing_record.get("Checker ID", "")
        
        if not team_name:
            team_name = existing_record.get("Team Name", "")
        
        breakdown_timestamp = existing_record.get("Timestamp Breakdown (CPCS)", "")
        if breakdown_timestamp and not record.pcs_received:
            current_timestamp = breakdown_timestamp
    
    # Prepare the row data with all values preserved
    row_data = [
        record.flight_number or "",
        record.scheduled_arrival_time.isoformat() if hasattr(record.scheduled_arrival_time, 'isoformat') else record.scheduled_arrival_time or "",
        record.actual_arrival_time.isoformat() if hasattr(record.actual_arrival_time, 'isoformat') else record.actual_arrival_time or "",
        record.mawb,
        record.flight_origin or "",
        record.flight_destination or "",
        str(record.pcs_awb) if record.pcs_awb is not None else "",
        str(record.gross_weight) if record.gross_weight is not None else "",
        record.commodity_type or "",
        bt_number or "",    # BT Number
        timestamp_start or "", # Timestamp Handover
        trolley_staff_id or "",  # Trolley Staff ID
        str(record.pcs_received) if record.pcs_received is not None else "",
        discrepancy,
        checker_id or "",
        team_name or "",
        current_timestamp if record.pcs_received is not None else "",  # Timestamp Breakdown (CPCS)
    ]
    
    # Find the row where the MAWB matches (add 3 to account for header rows)
    row_index = next((idx + 3 for idx, row in enumerate(records) if row.get("MAWB") == record.mawb), None)

    try:
        if row_index:
            # Update the existing row
            worksheet.update(f"A{row_index}:Q{row_index}", [row_data])
            print(f"Updated row {row_index} for MAWB: {record.mawb}")
        else:
            # Append a new row
            worksheet.append_row(row_data)
            print(f"Appended new row for MAWB: {record.mawb}")
        
        # Reset all formatting first to remove any previous highlights
        clear_formatting(worksheet, row_index if row_index else worksheet.row_count)
        
        # Then apply highlighting for discrepancies if needed
        highlight_discrepancies(worksheet)
    except Exception as e:
        print(f"Error updating Google Sheet: {e}")

def clear_formatting(worksheet, row_index):
    """Clear formatting for a specific row."""
    try:
        worksheet.format(f"A{row_index}:Q{row_index}", {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1}  # White background
        })
    except Exception as e:
        print(f"Error clearing formatting: {e}")

def highlight_discrepancies(worksheet):
    """
    Highlights rows where 'No. of Pcs (AWB)' and 'No. of Pcs (Received)' do not match.
    Removes highlighting from rows where discrepancies have been resolved.
    """
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 3:  # Need at least header rows plus one data row
            return
            
        # Get the column header row (row 2)
        header = data[1]  # Index 1 is the second row
        pcs_awb_col = header.index("No. of Pcs (AWB)") + 1 if "No. of Pcs (AWB)" in header else None
        pcs_received_col = header.index("No. of Pcs (Received)") + 1 if "No. of Pcs (Received)" in header else None
        discrepancy_col = header.index("Discrepancy") + 1 if "Discrepancy" in header else None
        
        if not pcs_awb_col or not pcs_received_col or not discrepancy_col:
            print("Missing required columns in spreadsheet")
            return

        # Define format rules
        red_background = {
            "backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}
        }
        
        white_background = {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1}
        }

        # Start from row 3 (skip header rows)
        for i, row in enumerate(data[2:], start=3):
            try:
                # Check if there's a discrepancy in this row
                discrepancy = row[discrepancy_col - 1]
                
                if discrepancy == "Yes":
                    # Apply red background for discrepancy
                    worksheet.format(f"A{i}:Q{i}", red_background)
                else:
                    # Remove highlighting for rows without discrepancy
                    worksheet.format(f"A{i}:Q{i}", white_background)
            except (ValueError, IndexError) as e:
                print(f"Error processing row {i}: {e}")
                continue  # Skip invalid rows
    except Exception as e:
        print(f"Error highlighting discrepancies: {e}")

def generate_random_mawb():
    """Generate a random MAWB number."""
    return f"MAWB{''.join(random.choices(string.digits, k=4))}"

def generate_random_flight_number():
    """Generate a random flight number."""
    airlines = ["SQ", "CX", "BA", "UA", "EK", "LH", "QF", "SU", "TR", "KE"]
    return f"{random.choice(airlines)}{random.randint(100, 999)}"

def generate_random_date_time(days_range=7):
    """Generate a random date and time within the past few days."""
    now = datetime.now()
    random_days = random.randint(0, days_range)
    random_seconds = random.randint(0, 86400)  # 24 hours in seconds
    random_datetime = now - timedelta(days=random_days, seconds=random_seconds)
    return random_datetime.isoformat()

def generate_random_location():
    """Generate a random airport code."""
    airports = ["SIN", "HKG", "LHR", "JFK", "DXB", "FRA", "SYD", "DME", "BKK", "ICN"]
    return random.choice(airports)

def generate_random_commodity():
    """Generate a random commodity type."""
    commodities = ["Electronics", "Apparel", "Perishables", "Medical Supplies", 
                  "Auto Parts", "Machinery", "Chemicals", "Textiles", 
                  "Documents", "General Cargo"]
    return random.choice(commodities)

def populate_sheet_with_dummy_data(num_records=20):
    """
    Populate the Google Sheet with dummy data.
    This is useful for testing and demonstration purposes.
    """
    try:
        print("Authenticating with Google Sheets...")
        worksheet = authenticate_google_sheets()
        
        print(f"Populating with {num_records} dummy records...")
        
        for _ in range(num_records):
            # Generate scheduled and actual arrival times
            sta = generate_random_date_time()
            # Actual arrival time is usually close to scheduled
            ata = datetime.fromisoformat(sta) + timedelta(minutes=random.randint(-60, 120))
            ata = ata.isoformat()
            
            # Generate random AWB pieces but leave received pieces empty
            pcs_awb = random.randint(1, 100)
            
            # Other random data
            mawb = generate_random_mawb()
            flight_number = generate_random_flight_number()
            origin = generate_random_location()
            destination = generate_random_location()
            while destination == origin:  # Ensure different origin and destination
                destination = generate_random_location()
            
            gross_weight = round(random.uniform(10, 2000), 2)
            commodity = generate_random_commodity()
            
            # No discrepancy calculation since pieces received is empty
            discrepancy = "No"
            
            # Create the row data with updated column order and names
            row_data = [
                flight_number,
                sta,
                ata,
                mawb,
                origin,
                destination,
                str(pcs_awb),
                str(gross_weight),
                commodity,
                "",  # Empty "BT Number"
                "",  # Empty "Timestamp Handover"
                "",  # Empty "Trolley Staff ID"
                "",  # Empty "No. of Pcs (Received)"
                discrepancy,
                "",  # Empty "Checker ID"
                "",  # Empty "Team Name"
                ""   # Empty "Timestamp Breakdown (CPCS)"
            ]
            
            # Add row to sheet
            worksheet.append_row(row_data)
            print(f"Added row with MAWB: {mawb}, Pieces AWB: {pcs_awb}")
            
            # Short delay to avoid rate limits
            time.sleep(0.5)
            
        print(f"Successfully added {num_records} dummy records to the sheet.")
        return True
    except Exception as e:
        print(f"Error populating sheet with dummy data: {e}")
        import traceback
        traceback.print_exc()
        return False
