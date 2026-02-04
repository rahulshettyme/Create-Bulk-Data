import time
import requests
import json
import math
from datetime import datetime
import thread_utils

# Shared Google API Key from RS_address_generate
GOOGLE_API_KEY = "AIzaSyAwy--7hbQ9x-_rFT2lCi52o0rF0JvbA7E" 
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def get_location_details(address_text=None, lat=None, lng=None, address=None, latitude=None, longitude=None):
    # Support multiple signatures for compatibility
    addr_in = address_text or address
    lat_in = lat if lat is not None else latitude
    lng_in = lng if lng is not None else longitude
    
    if addr_in:
        params = {"address": addr_in, "key": GOOGLE_API_KEY}
    elif lat_in is not None and lng_in is not None:
        params = {"latlng": f"{lat_in},{lng_in}", "key": GOOGLE_API_KEY}
    else:
        return None

    try:
        # print(f"Calling Google Geocode API...") 
        response = requests.get(GEOCODE_URL, params=params)
        data = response.json()
        
        if response.status_code != 200 or not data.get("results"):
            return None

        result = data["results"][0]
        
        address_components = result.get("address_components", [])
        def get_component(types):
            for comp in address_components:
                if any(t in comp["types"] for t in types):
                    return comp.get("long_name", "")
            return ""

        geometry = result.get("geometry", {}).get("location", {})
        res_lat = geometry.get("lat", lat_in) 
        res_lng = geometry.get("lng", lng_in)

        address_out = {
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
        return address_out
    except Exception as e:
        print(f"Error fetching address: {e}")
        return None

# --- AUTO-GENERATED WRAPPER ---
def run(rows, token, env_config):
    start_time = datetime.now()
    
    # INJECTED CONFIGURATION
    env_name = env_config.get("environment", "Prod")
    base_url = env_config.get("apiBaseUrl")
    if not base_url:
        ENV_MAP = { "QA1": "https://qa1.cropin.in", "QA2": "https://qa2.cropin.in", "Prod": "" }
        base_url = ENV_MAP.get(env_name)
    
    print(f"🌍 Using Base URL: {base_url.rstrip('/')}")
    place_url = f"{base_url.rstrip('/')}/services/farm/api/place"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 🔧 Helper: validate coordinates
    def is_valid_coord(v):
        if v is None: return False
        if isinstance(v, str) and v.strip() == "": return False
        try:
            num = float(v)
            return math.isfinite(num)
        except Exception:
            return False

    # --- PROCESS ROW FUNCTION ---
    def process_row(row):
        # We work on a dictionary directly (mimicking the row)
        # Ensure we don't mutate the original input deeply if not needed, 
        # but here we return a modified copy or modify inplace (since list items assume independence)
        # Safest is copy
        new_row = row.copy()
        try:
            name = str(new_row.get("name", "")).strip()
            place_type = str(new_row.get("type", "")).strip().upper()
            lat_raw = new_row.get("latitude", None)
            lng_raw = new_row.get("longitude", None)
            address_text = ""
            if new_row.get("address") is not None:
                address_text = str(new_row.get("address")).strip()
    
            # Basic validation
            if not name or not place_type:
                new_row["status"] = "⚠️ Skipped - Missing required fields (name/type)"
                new_row["response"] = ""
                return new_row
    
            use_coords = is_valid_coord(lat_raw) and is_valid_coord(lng_raw)
            lat_val = float(lat_raw) if is_valid_coord(lat_raw) else None
            lng_val = float(lng_raw) if is_valid_coord(lng_raw) else None
    
            # Call address generator
            addr = None
            try:
                # Priority 1: Address + Coords
                addr = get_location_details(address_text, lat_val, lng_val)
                # Priority 2: Coords only
                if not addr and use_coords:
                     addr = get_location_details(lat=lat_val, lng=lng_val)
                # Priority 3: Address only
                if not addr and address_text:
                     addr = get_location_details(address_text=address_text)
                     
            except Exception as ex:
                print("❌ Unexpected error while calling get_location_details:", ex)
                addr = None
    
            if not addr:
                new_row["status"] = "❌ Failed: No address"
                new_row["response"] = "Address generator returned empty/falsy payload"
                return new_row
    
            lat_from_addr = float(addr.get("latitude")) if addr.get("latitude") is not None else None
            lon_from_addr = float(addr.get("longitude")) if addr.get("longitude") is not None else None
    
            payload = {
                "name": name,
                "type": place_type,
                "subType": None,
                "capacity": {"count": 10},
                "address": addr,
                "areaAudit": None,
                "auditedArea": None,
                "visibility": True,
                "latitude": lat_from_addr if lat_from_addr is not None else lat_val,
                "longitude": lon_from_addr if lon_from_addr is not None else lng_val,
                "data": None,
                "images": None
            }
    
            try:
                # print(f"➡️ Calling Add Place API for {name} ...")
                response = requests.post(place_url, headers=headers, json=payload)
                response_text = str(response.text)
                
                new_row["response"] = response_text
                if response.status_code in (200, 201):
                    new_row["status"] = "✅ Success"
                else:
                    new_row["status"] = f"❌ Failed: {response.status_code}"
            except Exception as api_ex:
                new_row["response"] = f"API call failed: {str(api_ex)}"
                new_row["status"] = "❌ Failed: API error"
                
        except Exception as e:
            new_row["status"] = f"⚠️ Error: {str(e)}"
            new_row["response"] = ""
            
        return new_row

    # Execute Parallel
    print(f"🚀 Starting parallel execution for {len(rows)} rows...")
    processed_rows = thread_utils.run_in_parallel(process_row, rows)
    
    end_time = datetime.now()
    print("\n🏁 Execution completed.")
    print(f"Elapsed: {end_time - start_time}")
    
    return processed_rows
