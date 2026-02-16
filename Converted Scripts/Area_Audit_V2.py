import json
import math
import random
import requests
import thread_utils

def run(rows, token, env_config):
    """
    Performs Area Audit for Croppable Areas.
    1. Generates 1-acre square coordinates.
    2. Calculates Area via Geo API.
    3. Converts Units (Acre <-> Hectare) based on User/Company config.
    4. Updates Area Audit Status on the backend.
    """
    
    # --- 1. CONFIGURATION ---
    base_url = env_config.get('apiBaseUrl') or env_config.get('apiurl')
    if not base_url:
         # Fallback Logic if not provided
         env_name = env_config.get('environment', 'Prod')
         ENV_MAP = { "QA1": "https://qa1.cropin.in", "QA2": "https://qa2.cropin.in", "Prod": "" }
         base_url = ENV_MAP.get(env_name)
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # --- 2. UNIT CONVERSION LOGIC (Fetch Once) ---
    conversion_factor = 1.0
    try:
        # A. Company Config (Hardcoded ID 1251 as per original)
        comp_res = requests.get(f"{base_url}/services/farm/api/companies/1251", headers=headers)
        if comp_res.status_code == 200:
            comp_data = comp_res.json()
            comp_unit = comp_data.get('data', {}).get('preferences', {}).get('areaUnits', 'acre').lower()
        else:
            comp_unit = 'acre'

        # B. Determine Factor
        # Need: Convert FROM GeoAPI(Acre) TO Company Unit (Target)
        # GeoAPI is always in Acres.
        if comp_unit in ['ha', 'hectare']:
            conversion_factor = 0.404686 # Acre to Hectare
        else:
            conversion_factor = 1.0      # Acre to Acre
            
    except Exception as e:
        print(f"Warning: Failed to determine unit conversion: {e}")

    # --- 3. COORDINATE UTILS ---
    ACRE_M2 = 4046.8564224
    
    # Dynamic Area Config
    try:
        user_area = float(env_config.get('area_size', 1.0))
    except:
        user_area = 1.0
        
    user_unit = str(env_config.get('area_unit', 'Acre')).lower()
    
    # Calculate target area in Square Meters
    # 1 Acre = 4046.8564 sqm
    # 1 Hectare = 10000 sqm
    
    target_area_m2 = ACRE_M2 # Default 1 acre
    
    if user_unit in ['hectare', 'ha']:
        target_area_m2 = user_area * 10000.0
    else:
        target_area_m2 = user_area * ACRE_M2

    def meters_per_degree(lat_deg):
        lat = lat_deg * math.pi / 180
        m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat) + 1.175 * math.cos(4 * lat) - 0.0023 * math.cos(6 * lat)
        m_per_deg_lon = 111412.84 * math.cos(lat) - 93.5 * math.cos(3 * lat) + 0.118 * math.cos(5 * lat)
        return m_per_deg_lat, m_per_deg_lon

    def generate_square_polygon(min_lon, min_lat, max_lon, max_lat):
        if min_lon is None: return None
        c_lon = min_lon + random.random() * (max_lon - min_lon)
        c_lat = min_lat + random.random() * (max_lat - min_lat)
        
        side_m = math.sqrt(target_area_m2) # Use dynamic area
        m_lat, m_lon = meters_per_degree(c_lat)
        half_dx = (side_m / m_lon) / 2
        half_dy = (side_m / m_lat) / 2
        
        corners = [
            [c_lon - half_dx, c_lat - half_dy],
            [c_lon + half_dx, c_lat - half_dy],
            [c_lon + half_dx, c_lat + half_dy],
            [c_lon - half_dx, c_lat + half_dy],
            [c_lon - half_dx, c_lat - half_dy]
        ]
        return [[corners]]

    # Parse Boundary
    boundary = env_config.get('boundary', {})
    
    def safe_float(v):
        try:
            val = float(v)
            return val
        except (ValueError, TypeError):
            return None

    min_lat = safe_float(boundary.get('minLat'))
    max_lat = safe_float(boundary.get('maxLat'))
    min_long = safe_float(boundary.get('minLong'))
    max_long = safe_float(boundary.get('maxLong'))
    
    # --- 4. PROCESSING FUNC ---
    def process_row(row):
        new_row = row.copy()
        try:
            ca_id = str(row.get('CA_ID') or row.get('CAID') or row.get('CA ID') or row.get('caId') or '').strip()
            ca_name = str(row.get('CAName') or '').strip()
            
            # UI Requirement: Dynamic UI Keys
            new_row['Name'] = ca_name
            new_row['Id'] = ca_id
            
            if not ca_id:
                new_row['Status'] = 'Fail'
                new_row['Response'] = 'Missing CA_ID'
                return new_row

            # A. Get/Generate Coordinates
            coords_str = row.get('Coordinates')
            coords = None
            if coords_str:
                try: 
                    coords = json.loads(coords_str)
                except: 
                    pass # Invalid JSON handling?
            
            if not coords:
                if min_lat is not None:
                    coords = generate_square_polygon(min_long, min_lat, max_long, max_lat)
                else:
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = 'No Coordinates provided and no Boundary set'
                    return new_row

            # Ensure MultiPolygon: [[[lon, lat]...]]
            if isinstance(coords, list) and isinstance(coords[0], list) and isinstance(coords[0][0], list) and isinstance(coords[0][0][0], (int, float)):
                 coords = [coords] # Upgrade Polygon to MultiPolygon

            # B. Call GeoUtil API
            geo_payload = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": { "coordinates": coords, "type": "MultiPolygon" }
                }]
            }
            
            geo_url = f"{base_url}/services/utilservice/api/geojson/area"
            geo_resp = requests.post(geo_url, json=geo_payload, headers=headers)
            
            if geo_resp.status_code != 200:
                raise Exception(f"GeoAPI Failed: {geo_resp.text}")
                
            geo_data = geo_resp.json()
            audited_area_raw = float(geo_data.get('auditedArea', 0))
            latitude = geo_data.get('latitude')
            longitude = geo_data.get('longitude')
            
            # C. Apply Conversion
            final_area = audited_area_raw * conversion_factor
            
            # D. Update Area Audit
            ca_payload = {
                "id": int(ca_id),
                "cropAudited": True,
                "latitude": latitude,
                "longitude": longitude,
                "auditedArea": { "count": final_area },
                "usableArea": { "count": final_area },
                "areaAudit": {
                    "geoInfo": geo_payload,
                    "latitude": latitude,
                    "longitude": longitude,
                    "channel": "mobile"
                }
            }
            
            audit_url = f"{base_url}/services/farm/api/croppable-areas/area-audit"
            audit_resp = requests.put(audit_url, json=ca_payload, headers=headers)
            
            if audit_resp.status_code == 200:
                new_row['Status'] = 'Pass'
                new_row['Response'] = audit_resp.json().get('message', 'Success')
                new_row['AuditedArea'] = round(final_area, 4)
                new_row['Latitude'] = latitude
                new_row['Longitude'] = longitude
                new_row['Coordinates'] = json.dumps(coords)
                new_row['GeoInfo'] = json.dumps(geo_payload)
            else:
                err_Msg = audit_resp.json().get('message', 'Unknown Error') or audit_resp.text
                new_row['Status'] = 'Fail'
                new_row['Response'] = err_Msg
                
            # E. Recalculate Yields (if columns exist)
            def get_val(r,  keys):
                for k in keys:
                    found = next((chk for chk in r.keys() if k.lower() in chk.lower()), None)
                    if found and r[found]:
                        try: return float(r[found])
                        except: pass
                return None

            if final_area > 0:
                exp_harvest = get_val(row, ['expected harvest', 'exp_harvest', 'expectedharvest'])
                re_harvest = get_val(row, ['re-estimated harvest', 're_harvest', 'reestimatedharvest', 're-estimated value'])
                
                if exp_harvest is not None:
                    new_row['expYield'] = round(exp_harvest / final_area, 2)
                if re_harvest is not None:
                    new_row['reYield'] = round(re_harvest / final_area, 2)

        except Exception as e:
            new_row['Status'] = 'Fail'
            new_row['Response'] = str(e)
            
        return new_row

    return thread_utils.run_in_parallel(process_row, rows)
