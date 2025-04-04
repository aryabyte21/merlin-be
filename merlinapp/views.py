import random
from datetime import datetime, timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import FlightRecord
from .serializers import FlightRecordSerializer
from .utils import update_google_sheet, authenticate_google_sheets
import logging

logger = logging.getLogger(__name__)

def random_flight_number():
    # generate a random flight number based on current time (STA simulation)
    base = datetime.now().strftime('%H%M')
    return f"RW{base}{random.randint(100, 999)}"

@api_view(['GET'])
def redwatch_api(request):
    """Dummy API to return a random flight number (RedWatch)."""
    flight_number = random_flight_number()
    data = {
        "flight_number": flight_number,
        "scheduled_arrival_time": (datetime.now() + timedelta(minutes=random.randint(30,120))).isoformat()
    }
    return Response(data)

@api_view(['GET'])
def smartkargo_api(request):
    """Dummy API to return random flight details (SmartKargo)."""
    now = datetime.now()
    data = {
        "actual_arrival_time": (now + timedelta(minutes=random.randint(20,100))).isoformat(),
        "mawb": f"MAWB{random.randint(1000, 9999)}",
        "flight_origin": random.choice(["JFK", "LAX", "ORD", "ATL"]),
        "flight_destination": random.choice(["LHR", "CDG", "FRA", "DXB"]),
        "pcs_awb": random.randint(50, 300),
        "gross_weight": round(random.uniform(1000.0, 5000.0), 2),
        "commodity_type": random.choice(["Electronics", "Clothing", "Automobile", "Pharma"]),
    }
    return Response(data)

@api_view(['POST'])
def merge_data(request):
    """
    Calls both dummy APIs, merges their data, saves into the FlightRecord,
    and updates the real Google Sheet.
    """
    # Get RedWatch data
    rw_response = redwatch_api(request)
    sk_response = smartkargo_api(request)
    
    # Merge data into one record
    merged_data = {
        "flight_number": rw_response.data.get("flight_number"),
        "scheduled_arrival_time": rw_response.data.get("scheduled_arrival_time"),
        "actual_arrival_time": sk_response.data.get("actual_arrival_time"),
        "mawb": sk_response.data.get("mawb"),
        "flight_origin": sk_response.data.get("flight_origin"),
        "flight_destination": sk_response.data.get("flight_destination"),
        "pcs_awb": sk_response.data.get("pcs_awb"),
        "gross_weight": sk_response.data.get("gross_weight"),
        "commodity_type": sk_response.data.get("commodity_type"),
        "pcs_received": None,  # to be updated by ground staff
    }
    
    serializer = FlightRecordSerializer(data=merged_data)
    if serializer.is_valid():
        record = serializer.save()
        # Update the Google Sheet with the new record
        update_google_sheet(record)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def update_received(request):
    """
    Endpoint for ground staff to update the number of pieces received.
    Expected JSON: { 
        "mawb": "<MAWB#>", 
        "pcs_received": <number>,
        "checker_id": "<ID>",
        "team_name": "<Team>" 
    }
    """
    mawb = request.data.get("mawb")
    pcs_received = request.data.get("pcs_received")
    checker_id = request.data.get("checker_id", "")
    team_name = request.data.get("team_name", "")
    
    print(f"Received update request for MAWB: {mawb}, Pieces: {pcs_received} from {checker_id} ({team_name})")
    
    if not mawb or pcs_received is None:
        return Response({"error": "Missing mawb or pcs_received"}, status=400)
    
    try:
        # First try to find it in the database
        try:
            record = FlightRecord.objects.get(mawb=mawb)
            print(f"Found record in database for MAWB: {mawb}")
        except FlightRecord.DoesNotExist:
            # If not in database, create a new record from sheet data
            print(f"Record not found in database, creating new record for MAWB: {mawb}")
            
            # Get data from the sheet - specify head=2 to use second row as headers
            worksheet = authenticate_google_sheets()
            sheet_records = worksheet.get_all_records(head=2)
            
            # Find the record with matching MAWB
            sheet_record = next((r for r in sheet_records if r.get("MAWB") == mawb), None)
            
            if not sheet_record:
                return Response({"error": f"MAWB {mawb} not found in records"}, status=404)
            
            # Parse datetime strings if they exist
            scheduled_arrival = None
            actual_arrival = None
            
            try:
                if sheet_record.get("Scheduled Arrival Time"):
                    scheduled_arrival = datetime.fromisoformat(sheet_record.get("Scheduled Arrival Time"))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse Scheduled Arrival Time: {sheet_record.get('Scheduled Arrival Time')}")
                
            try:
                if sheet_record.get("Actual Arrival Time"):
                    actual_arrival = datetime.fromisoformat(sheet_record.get("Actual Arrival Time"))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse Actual Arrival Time: {sheet_record.get('Actual Arrival Time')}")
            
            # Convert string numbers to integers/floats
            pcs_awb = None
            if sheet_record.get("No. of Pcs (AWB)"):
                try:
                    pcs_awb = int(sheet_record.get("No. of Pcs (AWB)"))
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse AWB pieces: {sheet_record.get('No. of Pcs (AWB)')}")
            
            gross_weight = None
            if sheet_record.get("Gross Weight"):
                try:
                    gross_weight = float(sheet_record.get("Gross Weight"))
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse Gross Weight: {sheet_record.get('Gross Weight')}")
            
            # Create a new database record
            record = FlightRecord(
                mawb=mawb,
                flight_number=sheet_record.get("Flight #"),
                scheduled_arrival_time=scheduled_arrival,
                actual_arrival_time=actual_arrival,
                flight_origin=sheet_record.get("Flight Origin"),
                flight_destination=sheet_record.get("Flight Destination"),
                pcs_awb=pcs_awb,
                gross_weight=gross_weight,
                commodity_type=sheet_record.get("Commodity Type"),
            )
        
        # Update the pieces received
        record.pcs_received = pcs_received
        record.save()
        
        # Update the Google Sheet
        print(f"Updating Google Sheet for MAWB: {mawb}")
        
        # Get BT data from the record
        bt_number = record.bt_number
        timestamp_start = record.timestamp_start.isoformat() if record.timestamp_start else None
        trolley_staff_id = record.trolley_staff_id
        
        # Pass all data when updating
        update_google_sheet(record, checker_id, team_name, bt_number, timestamp_start, trolley_staff_id)
        
        serializer = FlightRecordSerializer(record)
        return Response({"status": "success", "data": serializer.data})
    
    except Exception as e:
        print(f"Error updating record: {e}")
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
def batch_update_received(request):
    """Update multiple records at once"""
    records = request.data.get("records", [])
    results = []
    
    for record_data in records:
        mawb = record_data.get("mawb")
        pcs_received = record_data.get("pcs_received")
        
        try:
            record = FlightRecord.objects.get(mawb=mawb)
            record.pcs_received = pcs_received
            update_google_sheet(record)
            results.append({"mawb": mawb, "status": "success"})
        except Exception as e:
            results.append({"mawb": mawb, "status": "error", "message": str(e)})
    
    return Response({"results": results})

@api_view(['GET'])
def mawb_suggestions(request):
    """
    Returns a list of MAWB numbers that match the query.
    This endpoint is used for autocomplete suggestions in the frontend.
    """
    query = request.query_params.get('query', '').strip()
    print(f"Received MAWB suggestion request with query: '{query}'")
    
    if not query:
        print("Empty query, returning empty list")
        return Response([])
    
    try:
        print("Attempting to authenticate with Google Sheets...")
        # Get worksheet
        worksheet = authenticate_google_sheets()
        
        print("Fetching all records from sheet...")
        # Get all records - specify head=2 to use second row as headers
        records = worksheet.get_all_records(head=2)
        print(f"Found {len(records)} records in the sheet")
        
        # Extract MAWB numbers
        mawbs = [record.get('MAWB', '') for record in records if record.get('MAWB')]
        print(f"Extracted {len(mawbs)} MAWB numbers: {mawbs[:5]}...")
        
        # Filter based on query
        filtered_mawbs = [mawb for mawb in mawbs if query.lower() in mawb.lower()]
        print(f"Filtered to {len(filtered_mawbs)} matching MAWB numbers: {filtered_mawbs[:5]}...")
        
        # Return unique MAWB numbers
        result = list(set(filtered_mawbs))
        print(f"Returning {len(result)} unique MAWB numbers")
        return Response(result)
    except Exception as e:
        print(f"Error fetching MAWB suggestions: {e}")
        import traceback
        traceback.print_exc()
        return Response([], status=500)

@api_view(['POST'])
def populate_dummy_data(request):
    """
    Endpoint to clear and repopulate the Google Sheet with dummy data.
    The pieces received field will be left empty for all records.
    """
    try:
        from .utils import authenticate_google_sheets, populate_sheet_with_dummy_data
        
        # Get worksheet
        worksheet = authenticate_google_sheets()
        
        # Clear existing data (keep headers)
        records = worksheet.get_all_values()
        if len(records) > 2:  # Now we have 2 header rows
            # Clear all rows except headers
            worksheet.delete_rows(3, len(records))  # Start from row 3
            print("Cleared existing data from sheet")
        
        # Populate with new dummy data
        populate_sheet_with_dummy_data(num_records=20)  # Generate 20 records
        
        return Response({"status": "success", "message": "Sheet populated with dummy data"})
    except Exception as e:
        print(f"Error repopulating sheet: {e}")
        import traceback
        traceback.print_exc()
        return Response({"status": "error", "message": str(e)}, status=500)

@api_view(['POST', 'OPTIONS'])
def trolley_login(request):
    """
    Simple login endpoint for trolley guys.
    Requires only employee_id.
    """
    logger.info(f"Received trolley login request with method: {request.method}")
    
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    logger.info(f"Request data: {request.data}")
    
    # Get employee_id from request data
    employee_id = request.data.get("employee_id")
    
    logger.info(f"Extracted employee_id: {employee_id}")
    
    if not employee_id:
        return Response({"error": "Employee ID is required"}, status=400)
    
    # For demo, we'll just return success
    response_data = {
        "success": True,
        "user": {
            "employeeId": employee_id,
            "role": "trolley"
        }
    }
    logger.info(f"Sending response: {response_data}")
    return Response(response_data)

@api_view(['GET'])
def flight_suggestions(request):
    """
    Returns a list of flight numbers that match the query.
    This endpoint is used for autocomplete suggestions in the trolley interface.
    """
    query = request.query_params.get('query', '').strip()
    print(f"Received flight suggestion request with query: '{query}'")
    
    if not query:
        print("Empty query, returning empty list")
        return Response([])
    
    try:
        print("Attempting to authenticate with Google Sheets...")
        # Get worksheet
        worksheet = authenticate_google_sheets()
        
        print("Fetching all records from sheet...")
        # Get all records - specifying we want to use the second row as headers
        records = worksheet.get_all_records(head=2)
        print(f"Found {len(records)} records in the sheet")
        
        # Extract flight numbers
        flights = [record.get('Flight #', '') for record in records if record.get('Flight #')]
        print(f"Extracted {len(flights)} flight numbers")
        
        # Filter based on query
        filtered_flights = [flight for flight in flights if query.lower() in flight.lower()]
        print(f"Filtered to {len(filtered_flights)} matching flight numbers")
        
        # Return unique flight numbers
        result = list(set(filtered_flights))
        print(f"Returning {len(result)} unique flight numbers")
        return Response(result)
    except Exception as e:
        print(f"Error fetching flight suggestions: {e}")
        import traceback
        traceback.print_exc()
        return Response([], status=500)

@api_view(['GET'])
def mawb_by_flight(request):
    """
    Returns a list of MAWB numbers for a specific flight.
    This is used when a trolley guy selects a flight and needs to see associated AWBs.
    """
    flight = request.query_params.get('flight', '').strip()
    print(f"Received MAWB by flight request with flight: '{flight}'")
    
    if not flight:
        print("Empty flight parameter, returning empty list")
        return Response([])
    
    try:
        print("Attempting to authenticate with Google Sheets...")
        # Get worksheet
        worksheet = authenticate_google_sheets()
        
        print("Fetching all records from sheet...")
        # Get all records - specify head=2 to use second row as headers
        records = worksheet.get_all_records(head=2)
        print(f"Found {len(records)} records in the sheet")
        
        # Filter records by flight number
        flight_records = [r for r in records if r.get('Flight #') == flight]
        print(f"Found {len(flight_records)} records for flight {flight}")
        
        # Extract MAWB numbers
        mawbs = [record.get('MAWB', '') for record in flight_records if record.get('MAWB')]
        
        return Response(mawbs)
    except Exception as e:
        print(f"Error fetching MAWBs by flight: {e}")
        import traceback
        traceback.print_exc()
        return Response([], status=500)

@api_view(['POST'])
def update_bt_number(request):
    """
    Endpoint for trolley guys to update the BT number for a specific MAWB.
    Expected JSON: { 
        "mawb": "<MAWB#>", 
        "bt_number": "<BT#>",
        "employee_id": "<ID>"
    }
    """
    mawb = request.data.get("mawb")
    bt_number = request.data.get("bt_number")
    employee_id = request.data.get("employee_id", "")
    
    print(f"Received BT update request for MAWB: {mawb}, BT: {bt_number} from {employee_id}")
    
    if not mawb or not bt_number:
        return Response({"error": "Missing mawb or bt_number"}, status=400)
    
    try:
        # First try to find it in the database
        try:
            record = FlightRecord.objects.get(mawb=mawb)
            print(f"Found record in database for MAWB: {mawb}")
        except FlightRecord.DoesNotExist:
            # If not in database, create a new record from sheet data
            print(f"Record not found in database, creating new record for MAWB: {mawb}")
            
            # Get data from the sheet
            worksheet = authenticate_google_sheets()
            sheet_records = worksheet.get_all_records(head=2)
            
            # Find the record with matching MAWB
            sheet_record = next((r for r in sheet_records if r.get("MAWB") == mawb), None)
            
            if not sheet_record:
                return Response({"error": f"MAWB {mawb} not found in records"}, status=404)
            
            # Parse datetime strings if they exist
            scheduled_arrival = None
            actual_arrival = None
            
            try:
                if sheet_record.get("Scheduled Arrival Time"):
                    scheduled_arrival = datetime.fromisoformat(sheet_record.get("Scheduled Arrival Time"))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse Scheduled Arrival Time: {sheet_record.get('Scheduled Arrival Time')}")
                
            try:
                if sheet_record.get("Actual Arrival Time"):
                    actual_arrival = datetime.fromisoformat(sheet_record.get("Actual Arrival Time"))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse Actual Arrival Time: {sheet_record.get('Actual Arrival Time')}")
            
            # Convert string numbers to integers/floats
            pcs_awb = None
            if sheet_record.get("No. of Pcs (AWB)"):
                try:
                    pcs_awb = int(sheet_record.get("No. of Pcs (AWB)"))
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse AWB pieces: {sheet_record.get('No. of Pcs (AWB)')}")
            
            gross_weight = None
            if sheet_record.get("Gross Weight"):
                try:
                    gross_weight = float(sheet_record.get("Gross Weight"))
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse Gross Weight: {sheet_record.get('Gross Weight')}")
            
            # Create a new database record
            record = FlightRecord(
                mawb=mawb,
                flight_number=sheet_record.get("Flight #"),
                scheduled_arrival_time=scheduled_arrival,
                actual_arrival_time=actual_arrival,
                flight_origin=sheet_record.get("Flight Origin"),
                flight_destination=sheet_record.get("Flight Destination"),
                pcs_awb=pcs_awb,
                gross_weight=gross_weight,
                commodity_type=sheet_record.get("Commodity Type"),
                pcs_received=sheet_record.get("No. of Pcs (Received)") or None,
            )
        
        # Update the BT number
        record.bt_number = bt_number
        record.trolley_staff_id = employee_id
        record.timestamp_start = datetime.now()
        record.save()
        
        # Generate timestamp for BT number submission
        timestamp_start = datetime.now().isoformat()
        
        # Update the Google Sheet
        print(f"Updating Google Sheet with BT number for MAWB: {mawb}")
        update_google_sheet(record, None, None, bt_number, timestamp_start, employee_id)
        
        return Response({
            "status": "success", 
            "message": f"Updated BT number for MAWB {mawb}",
            "timestamp": timestamp_start
        })
    
    except Exception as e:
        print(f"Error updating BT number: {e}")
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)
