import json
import attribute_utils
import time
import requests
import thread_utils

# Shared Google API Key from RS_address_generate


# Shared Google API Key from RS_address_generate
GOOGLE_API_KEY = "AIzaSyAwy--7hbQ9x-_rFT2lCi52o0rF0JvbA7E" 
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def get_location_details(address_text=None, lat=None, lng=None):
    if address_text:
        params = {"address": address_text, "key": GOOGLE_API_KEY}
    elif lat is not None and lng is not None:
        params = {"latlng": f"{lat},{lng}", "key": GOOGLE_API_KEY}
    else:
        return None

    try:
        print(f"Calling Google Geocode API: {GEOCODE_URL} with params: { {k:(v if k!='key' else '***') for k,v in params.items()} }")
        response = requests.get(GEOCODE_URL, params=params)
        data = response.json()
        
        print(f"Google API Status: {response.status_code}")
        if response.status_code != 200 or not data.get("results"):
            print(f"Google API No Results or Error: {json.dumps(data)}")
            return None

        result = data["results"][0]
        
        # Safe component extraction
        address_components = result.get("address_components", [])
        def get_component(types):
            for comp in address_components:
                if any(t in comp["types"] for t in types):
                    return comp.get("long_name", "")
            return ""

        geometry = result.get("geometry", {}).get("location", {})
        res_lat = geometry.get("lat", lat) # Use API lat or fallback
        res_lng = geometry.get("lng", lng) # Use API lng or fallback

        address = {
            "country": get_component(["country"]),
            "formattedAddress": result.get("formatted_address", ""),
            "administrativeAreaLevel1": get_component(["administrative_area_level_1"]),
            "administrativeAreaLevel2": get_component(["administrative_area_level_2"]),
            "locality": get_component(["locality"]),
            "sublocalityLevel1": get_component(["sublocality_level_1"]),
            "sublocalityLevel2": get_component(["sublocality_level_2"]),
            "landmark": "",
            "postalCode": get_component(["postal_code"]),
            "houseNo": "",
            "buildingName": "",
            "placeId": result.get("place_id", ""),
            "latitude": res_lat,
            "longitude": res_lng
        }
        return address
    except Exception as e:
        print(f"Error fetching address: {e}")
        return None

def run(rows, token, env_config):
    """
    Creates Farmers.
    1. Geocodes Address (Server-side Google API).
    2. Constructs Multipart DTO.
    3. Calls Create Farmer API.
    """
    
    # Config
    base_url = env_config.get('apiBaseUrl')
    if not base_url:
         env_name = env_config.get('environment', 'Prod')
         ENV_MAP = { "QA1": "https://qa1.cropin.in", "QA2": "https://qa2.cropin.in", "Prod": "" }
         base_url = ENV_MAP.get(env_name)
    
    print(f"1. Environment API URL used: {base_url}")
    farmer_url = f"{base_url}/services/farm/api/farmers"
    
    # Headers (Requests handles Content-Type for multipart)
    frontend_url = env_config.get('frontendUrl') or base_url
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'origin': frontend_url,
        'referer': f"{frontend_url}/"
    }

    print(f"Executing against URL: {farmer_url}")
    
    # Extract Additional Attributes
    additional_attributes = env_config.get('additionalAttributes', [])
    print(f"Additional Attributes configured: {additional_attributes}")

    # --- PROCESS ROW FUNCTION ---
    def process_row(row):
        new_row = row.copy()
        try:
            # 1. Parse Inputs
            name = str(row.get('Farmer Name') or row.get('Name') or '').strip()
            code = str(row.get('Farmer Code') or row.get('Code') or '').strip()
            phone = str(row.get('Phone Number') or row.get('Mobile') or '').strip()
            assigned_to = str(row.get('AssignedTo') or row.get('Agent ID') or '').strip()
            address_text = str(row.get('Address') or row.get('Farmer Address') or row.get('Location') or '').strip()
            
            # Coordinate Support (matching RS_address_generate style)
            lat_val = row.get('Latitude') or row.get('Lat')
            lng_val = row.get('Longitude') or row.get('Lng') or row.get('Lon') or row.get('Long')
            
            if not code or not phone:
                 new_row['Status'] = 'Fail'
                 new_row['API_Response'] = 'Missing Farmer Code or Phone'
                 return new_row
                 
            # Phone Parse
            parts = phone.split()
            if len(parts) > 1:
                cc = '+' + parts[0].replace('+','')
                mob = parts[1]
            else:
                cc = "+91"
                mob = phone.replace(' ', '')
                
                # 2. Geocode
            address_json = {}
            if address_text or (lat_val and lng_val):
                if lat_val and lng_val:
                    print(f"Geocoding via Lat/Lng: {lat_val}, {lng_val}")
                    address_json = get_location_details(lat=lat_val, lng=lng_val)
                else:
                    print(f"Geocoding via Address: {address_text}")
                    address_json = get_location_details(address_text=address_text)
                
                print(f"2. Address attribute formed from the address in excel: {json.dumps(address_json)}")
                time.sleep(0.1) # Rate limit niceness
                
                # Validation Fallback
                if not address_json or not address_json.get('formattedAddress'):
                    print("Geocoding failed/returned empty. Using raw text as fallback.")
                    fallback_text = address_text if address_text else f"{lat_val},{lng_val}"
                    address_json = {
                        "formattedAddress": fallback_text,
                        "latitude": float(lat_val) if lat_val else 0,
                        "longitude": float(lng_val) if lng_val else 0
                    }
                
                # Update row with geocode details
                new_row['Formatted Address'] = address_json.get('formattedAddress')
                new_row['Latitude'] = address_json.get('latitude')
                new_row['Longitude'] = address_json.get('longitude')
                new_row['address_json'] = json.dumps(address_json)
            
            # 3. Construct Payload
            payload = {
                "data": { "mobileNumber": mob, "countryCode": cc },
                "firstName": name,
                "farmerCode": code,
                "address": address_json,
                "assignedTo": [{ "id": int(assigned_to) }] if assigned_to.isdigit() else []
            }
            
            # Add GDPR Flag if enabled
            if env_config.get('isGDPRCompliant'):
                payload['isGDPRCompliant'] = True
            
            # Add Additional Attributes using Shared Helper
            payload = attribute_utils.add_attributes_to_payload(row, payload, env_config, target_key='data')
            
            # 4. API Call (Multipart)
            files = {
                'dto': ('body.json', json.dumps(payload), 'application/json')
            }
            
            print(f"5. Payload created and the api hit: {json.dumps(payload)} to {farmer_url}")
            resp = requests.post(farmer_url, headers=headers, files=files)
            
            print(f"6. Response of the api: {resp.text}")
            if resp.status_code in [200, 201]:
                # Attempt to parse json
                try:
                    res_json = resp.json()
                    new_row['Status'] = 'Pass'
                    new_row['API_Response'] = json.dumps(res_json)
                except:
                    new_row['Status'] = 'Pass'
                    new_row['API_Response'] = 'Success'
            else:
                msg = resp.text
                print(f"Server Error ({resp.status_code}): {msg}")
                try:
                    err = resp.json()
                    msg = err.get('message') or err.get('error') or err.get('title') or msg
                except:
                    pass
                new_row['Status'] = 'Fail'
                new_row['API_Response'] = msg
                
        except Exception as e:
            new_row['Status'] = 'Fail'
            new_row['API_Response'] = str(e)
            
        return new_row

    return thread_utils.run_in_parallel(process_row, rows)
