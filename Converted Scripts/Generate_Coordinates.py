import json
import math
import random

def run(rows, token, env_config):
    """
    Generates 1-acre square coordinates for each row within a provided bounding box.
    """
    processed_rows = []
    
    # 1. Parse Boundary from Config
    boundary = env_config.get('boundary')
    if not boundary or 'minLat' not in boundary:
        # If no boundary provided, we can't generate.
        # Check if rows have lat/long hints? No, requirement is 'Generate'.
        pass 
        # We will iterate and error out for rows, or rely on defaults if requested.
        # For now, let's assume if it fails, we mark status 'Fail'.

    bbox_valid = False
    if boundary:
        min_lat = boundary.get('minLat')
        max_lat = boundary.get('maxLat')
        min_long = boundary.get('minLong')
        max_long = boundary.get('maxLong')
        if all(x is not None for x in [min_lat, max_lat, min_long, max_long]):
            bbox_valid = True

    ACRE_M2 = 4046.8564224

    def meters_per_degree(lat_deg):
        lat = lat_deg * math.pi / 180
        # WGS84 approx
        m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat) + 1.175 * math.cos(4 * lat) - 0.0023 * math.cos(6 * lat)
        m_per_deg_lon = 111412.84 * math.cos(lat) - 93.5 * math.cos(3 * lat) + 0.118 * math.cos(5 * lat)
        return m_per_deg_lat, m_per_deg_lon

    def generate_square_one_acre(min_lon, min_lat, max_lon, max_lat):
        # Random center
        c_lon = min_lon + random.random() * (max_lon - min_lon)
        c_lat = min_lat + random.random() * (max_lat - min_lat)

        side_m = math.sqrt(ACRE_M2)
        m_lat, m_lon = meters_per_degree(c_lat)
        
        d_lat = side_m / m_lat
        d_lon = side_m / m_lon
        
        half_dx = d_lon / 2
        half_dy = d_lat / 2
        
        corners = [
            [c_lon - half_dx, c_lat - half_dy],
            [c_lon + half_dx, c_lat - half_dy],
            [c_lon + half_dx, c_lat + half_dy],
            [c_lon - half_dx, c_lat + half_dy],
            [c_lon - half_dx, c_lat - half_dy] # Close loop
        ]
        
        return [[corners]] # MultiPolygon format

    for i, row in enumerate(rows):
        # Normalize keys
        ca_name = row.get('CAName') or row.get('CA Name') or row.get('caName') or ''
        ca_id = row.get('CA_ID') or row.get('CAID') or row.get('CA ID') or row.get('caId') or ''
        
        # Prepare result row
        new_row = row.copy()
        
        # Validate Identity
        if not ca_name and not ca_id:
            new_row['Status'] = 'Fail'
            new_row['API_Response'] = 'Missing CAName or CA_ID'
            processed_rows.append(new_row)
            continue

        if not bbox_valid:
            new_row['Status'] = 'Fail'
            new_row['API_Response'] = 'Boundary Not Configured in Settings'
            processed_rows.append(new_row)
            continue
            
        try:
            coords = generate_square_one_acre(min_long, min_lat, max_long, max_lat)
            coords_json = json.dumps(coords)
            
            new_row['Coordinates'] = coords_json
            new_row['Status'] = 'Pass'
            new_row['API_Response'] = 'Generated Coordinates'
            
        except Exception as e:
            new_row['Status'] = 'Fail'
            new_row['API_Response'] = str(e)
            
        processed_rows.append(new_row)

    return processed_rows
