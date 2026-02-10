import requests
import json


def _construct_polygon_from_bounds(bounds):
    if not bounds: return None
    ne = bounds.get('northeast')
    sw = bounds.get('southwest')
    
    if not ne or not sw: return None
    
    sw_lng = sw['lng']
    ne_lng = ne['lng']
    
    # Handle Date Line Crossing (Normalize/Unwrap)
    # If SW > NE (e.g. 166 > -66), it implies wrapping across 180.
    # We unwrap SW to negative (e.g. 166 - 360 = -194) to create a continuous linear box.
    if sw_lng > ne_lng:
        sw_lng -= 360.0

    # Create Box
    coords = [
        [sw_lng, sw['lat']],
        [ne_lng, sw['lat']],
        [ne_lng, ne['lat']],
        [sw_lng, ne['lat']],
        [sw_lng, sw['lat']]
    ]
    
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        }]
    }

def parse_address_component(geocode_result):
    """
    Transforms raw Google Geocoding API result into a standardized address component format.
    Returns ALL available data so scripts can pick what they need based on their requirements.
    
    Args:
        geocode_result: The result object from get_boundary() (data['results'][0])
        
    Returns:
        dict: Comprehensive address component with all available fields from Google API
    """
    if not geocode_result:
        return None
    
    # Helper function to extract component by type
    def get_component(components, type_name):
        for comp in components:
            if type_name in comp.get('types', []):
                return comp.get('long_name', '')
        return ''
    
    address_components = geocode_result.get('address_components', [])
    geometry = geocode_result.get('geometry', {})
    location = geometry.get('location', {})
    bounds = geometry.get('bounds')
    viewport = geometry.get('viewport')
    
    # Return comprehensive data - scripts can pick what they need
    result = {
        # Basic address info
        "formattedAddress": geocode_result.get('formatted_address', ''),
        "placeId": geocode_result.get('place_id', ''),
        
        # Location coordinates
        "latitude": location.get('lat'),
        "longitude": location.get('lng'),
        
        # Administrative areas (all levels)
        "country": get_component(address_components, 'country'),
        "administrativeAreaLevel1": get_component(address_components, 'administrative_area_level_1'),
        "administrativeAreaLevel2": get_component(address_components, 'administrative_area_level_2'),
        "administrativeAreaLevel3": get_component(address_components, 'administrative_area_level_3'),
        "administrativeAreaLevel4": get_component(address_components, 'administrative_area_level_4'),
        "administrativeAreaLevel5": get_component(address_components, 'administrative_area_level_5'),
        
        # Locality info
        "locality": get_component(address_components, 'locality'),
        "sublocalityLevel1": get_component(address_components, 'sublocality_level_1'),
        "sublocalityLevel2": get_component(address_components, 'sublocality_level_2'),
        "sublocalityLevel3": get_component(address_components, 'sublocality_level_3'),
        "sublocalityLevel4": get_component(address_components, 'sublocality_level_4'),
        "sublocalityLevel5": get_component(address_components, 'sublocality_level_5'),
        
        # Postal and route info
        "postalCode": get_component(address_components, 'postal_code'),
        "route": get_component(address_components, 'route'),
        "streetNumber": get_component(address_components, 'street_number'),
        
        # Additional fields that may be needed
        "premise": get_component(address_components, 'premise'),
        "subpremise": get_component(address_components, 'subpremise'),
        "neighborhood": get_component(address_components, 'neighborhood'),
        "colloquialArea": get_component(address_components, 'colloquial_area'),
        
        # Geometry data (bounds and viewport)
        "bounds": bounds,  # May be None if not available
        "viewport": viewport,  # Always available
        
        # Location type and other metadata
        "locationType": geometry.get('location_type'),
        
        # Placeholder fields for custom data (scripts can populate these)
        "id": None,
        "data": None,
        "houseNo": "",
        "buildingName": "",
        "landmark": "",
        "clientId": None
    }
    
    return result

def get_boundary(location_name, api_key):
    """
    Fetches the bounding box for a location name using Google Geocoding API.
    Returns: { 'northeast': {lat, lng}, 'southwest': {lat, lng} } or None
    """
    if not location_name or not api_key:
        return None
        
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": location_name,
        "key": api_key
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        masked_key = api_key[:5] + "***" if api_key and len(api_key) > 5 else "None/Empty"
        err_msg = data.get('error_message', '')
        print(f"[GEOFENCE V2] API Result for {location_name}: Status={data.get('status')} | Key={masked_key} | Msg={err_msg}")
        
        if "API is not activated" in err_msg:
            print(f"[GEOFENCE V2] 🔴 ACTION REQUIRED: Enable 'Geocoding API' here: https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com")
        
        if data['status'] == 'OK':
            result = data['results'][0]
            geometry = result.get('geometry', {})
            
            # Return Generic/Raw Result + Helper Polygon
            # We do NOT hardcode output schema here. The script must parse this generic data.
            result['geojson_polygon'] = _construct_polygon_from_bounds(geometry.get('bounds') or geometry.get('viewport'))
            return result
        else:
            return None
    except Exception as e:
        print(f"[GEOFENCE V2] Connection Error: {e}")
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
