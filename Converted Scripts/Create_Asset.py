import json
import attribute_utils
import time
import requests

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

import thread_utils

def run(rows, token, env_config):
    # 1. Config
    base_url = env_config.get('apiBaseUrl')
    if not base_url:
         env_name = env_config.get('environment', 'Prod')
         ENV_MAP = { "QA1": "https://qa1.cropin.in", "QA2": "https://qa2.cropin.in", "Prod": "" }
         base_url = ENV_MAP.get(env_name)
         
    print(f"1. Environment API URL used: {base_url}")
    frontend_url = env_config.get('frontendUrl') or base_url
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'origin': frontend_url,
        'referer': f"{frontend_url}/"
    }

    # 2. Fetch Reference Data (One-time)
    farmer_lookup_url = f"{base_url}/services/farm/api/farmers/dropdownList"
    print(f"3. Complete API used to find the farmers: {farmer_lookup_url}")
    
    # helper
    def fetch_ref(endpoint):
        try:
            r = requests.get(f"{base_url}{endpoint}", headers=headers)
            if r.status_code == 200:
                data = r.json()
                # Handle both direct array and {'data': [...]} wrapper
                if isinstance(data, list): return data
                if isinstance(data, dict): return data.get('data', [])
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
        return []

    farmers = fetch_ref("/services/farm/api/farmers/dropdownList")
    soil_types = fetch_ref("/services/farm/api/soil-types")
    irrigation_types = fetch_ref("/services/farm/api/irrigation-types")
    
    # Build Lookups
    id_map = {}
    code_map = {}
    for f in farmers:
        fid = f.get('id')
        fcode = f.get('farmerCode') or f.get('code')
        if fid:
            id_map[str(fid).strip()] = fid
        if fcode:
            code_map[str(fcode).strip().lower()] = fid
            
    print(f"Loaded {len(farmers)} farmers into lookup (IDs: {len(id_map)}, Codes: {len(code_map)}).")
    
    soil_map = { str(s.get('name','')).lower().strip(): s.get('id') for s in soil_types }
    irrigation_map = { str(i.get('name','')).lower().strip(): i.get('id') for i in irrigation_types }
    
    # Endpoint
    asset_url = f"{base_url}/services/farm/api/assets"
    print(f"Executing against URL: {asset_url}")

    # Extract Additional Attributes
    additional_attributes = env_config.get('additionalAttributes', [])
    print(f"Additional Attributes configured: {additional_attributes}")

    # --- PROCESS ROW FUNCTION (For Threading) ---
    def process_row(row):
        new_row = row.copy()
        try:
            # Inputs
            asset_name = str(row.get('Asset Name') or row.get('Name') or '').strip()
            # Farmer Code or ID
            f_code = str(row.get('Farmer Code') or row.get('Code') or '').strip()
            f_id_raw = str(row.get('Farmer ID') or '').strip()
            
            s_type = str(row.get('Soil Type') or '').strip()
            i_type = str(row.get('Irrigation Type') or '').strip()
            addr_text = str(row.get('Address') or row.get('Farmer Address') or row.get('Location') or '').strip()
            area_str = str(row.get('Declared Area') or row.get('Area') or '0').replace(',','')

            # Coordinate Support
            lat_val = row.get('Latitude') or row.get('Lat')
            lng_val = row.get('Longitude') or row.get('Lng') or row.get('Lon') or row.get('Long')
            
            # Validation
            missing = []
            if not asset_name: missing.append('Asset Name')
            if not f_code and not f_id_raw: missing.append('Farmer Code/ID')
            if not s_type: missing.append('Soil Type')
            if not i_type: missing.append('Irrigation Type')
            if not addr_text and not (lat_val and lng_val): missing.append('Address or Lat/Lng')
            
            if missing:
                new_row['Status'] = 'Fail'
                new_row['API_Response'] = f"Missing: {', '.join(missing)}"
                return new_row
                
            # Resolve IDs
            farmer_identifier = f_id_raw if f_id_raw else f_code
            print(f"4. Attribute used to get the farmer details: {farmer_identifier}")
            owner_id = None
            
            # Prefer matching column to attribute
            if f_id_raw:
                owner_id = id_map.get(f_id_raw)
            
            if not owner_id and f_code:
                owner_id = code_map.get(f_code.lower())
            
            if not owner_id:
                new_row['Status'] = 'Fail'
                msg = f"Farmer not found: {farmer_identifier}"
                new_row['API_Response'] = msg
                print(f"6. Response of the API (Lookup Failure): {msg}")
                return new_row
                
            soil_id = soil_map.get(s_type.lower())
            if not soil_id:
                new_row['Status'] = 'Fail'
                new_row['API_Response'] = f"Invalid Soil Type: {s_type}"
                return new_row

            irr_id = irrigation_map.get(i_type.lower())
            if not irr_id:
                new_row['Status'] = 'Fail'
                new_row['API_Response'] = f"Invalid Irrigation Type: {i_type}"
                return new_row
                
            # Geocode
            addr_json = {}
            if addr_text or (lat_val and lng_val):
                if lat_val and lng_val:
                    print(f"Geocoding via Lat/Lng: {lat_val}, {lng_val}")
                    addr_json = get_location_details(lat=lat_val, lng=lng_val)
                else:
                    print(f"Geocoding via Address: {addr_text}")
                    addr_json = get_location_details(address_text=addr_text)
                
                print(f"2. Address attribute formed from the address in excel: {json.dumps(addr_json)}")
                time.sleep(0.1)
                
                if not addr_json or not addr_json.get('formattedAddress'):
                    print("Geocoding failed/returned empty. Using raw text as fallback.")
                    fallback_text = addr_text if addr_text else f"{lat_val},{lng_val}"
                    addr_json = {
                        "formattedAddress": fallback_text,
                        "latitude": float(lat_val) if lat_val else 0,
                        "longitude": float(lng_val) if lng_val else 0
                    }
                
                # Update row with geocode details
                new_row['Formatted Address'] = addr_json.get('formattedAddress')
                new_row['Latitude'] = addr_json.get('latitude')
                new_row['Longitude'] = addr_json.get('longitude')
                new_row['address_json'] = json.dumps(addr_json)
            
            # Payload
            payload = {
                "declaredArea": { "count": float(area_str) if area_str else 0 },
                "name": asset_name,
                "ownerId": owner_id,
                "soilType": { "id": soil_id },
                "irrigationType": { "id": irr_id },
                "address": addr_json
            }
            
            # Add Additional Attributes to Payload using Shared Helper
            # Target key is None to add to root of payload
            payload = attribute_utils.add_attributes_to_payload(row, payload, env_config, target_key=None)
            
            # API Call
            files = { 'dto': ('body.json', json.dumps(payload), 'application/json') }
            print(f"5. Payload created and the api hit: {json.dumps(payload)} to {asset_url}")
            resp = requests.post(asset_url, headers=headers, files=files)
            
            print(f"6. Response of the api: {resp.text}")
            if resp.status_code in [200, 201]:
                 new_row['Status'] = 'Pass'
                 try: new_row['API_Response'] = json.dumps(resp.json())
                 except: new_row['API_Response'] = 'Success'
            else:
                 msg = resp.text
                 print(f"Server Error ({resp.status_code}): {msg}")
                 try: 
                     err = resp.json()
                     msg = err.get('message') or err.get('error') or err.get('title') or msg
                 except: pass
                 new_row['Status'] = 'Fail'
                 new_row['API_Response'] = msg
                 
        except Exception as e:
            new_row['Status'] = 'Fail'
            new_row['API_Response'] = str(e)
            
        return new_row

    # Execute in Parallel
    return thread_utils.run_in_parallel(process_row, rows)

