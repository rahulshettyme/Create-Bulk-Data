import requests
import json


def get_boundary(location_name, api_key):
    """
    Fetches the bounding box for a location name using Google Geocoding API.
    Returns: { 'northeast': {lat, lng}, 'southwest': {lat, lng} } or None
    """
    if not location_name or not api_key:
        return None
        
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location_name}&key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        masked_key = api_key[:5] + "***" if api_key and len(api_key) > 5 else "None/Empty"
        err_msg = data.get('error_message', '')
        print(f"[GEOFENCE] API Result for {location_name}: Status={data.get('status')} | Key={masked_key} | Msg={err_msg}")
        
        if "API is not activated" in err_msg:
            print(f"[GEOFENCE] 🔴 ACTION REQUIRED: Enable 'Geocoding API' here: https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com")
        
        if data['status'] == 'OK':
            result = data['results'][0]
            geometry = result.get('geometry', {})
            return geometry.get('bounds') or geometry.get('viewport')
        else:
            return None
    except Exception as e:
        print(f"[GEOFENCE] Connection Error: {e}")
        return None

def is_point_in_polygon(lat, lon, polygon):
    x, y = lat, lon
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_inside_boundary(lat, lon, boundary):
    if not boundary:
        return True
    ne = boundary['northeast']
    sw = boundary['southwest']
    lat_ok = sw['lat'] <= lat <= ne['lat']
    if sw['lng'] <= ne['lng']:
        lon_ok = sw['lng'] <= lon <= ne['lng']
    else:
        lon_ok = lon >= sw['lng'] or lon <= ne['lng']
    return lat_ok and lon_ok

def check_geofence(lat, lon, location_name, api_key, cache=None):
    if not location_name:
        return "N/A", True
        
    normalized_name = str(location_name).strip().lower()
    
    # Try API
    boundary = None
    if cache is not None and location_name in cache:
        boundary = cache[location_name]
    else:
        boundary = get_boundary(location_name, api_key)
        if cache is not None: cache[location_name] = boundary
        
    if boundary:
        return location_name, is_inside_boundary(lat, lon, boundary)
    
    
    # Otherwise pass by default to avoid blocking
    return f"Error ({location_name})", True
