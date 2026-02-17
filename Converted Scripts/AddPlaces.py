# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = False
# EXPECTED_INPUT_COLUMNS: name, type, tags, tag_id, latitude, longitude, address

def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import requests
    import json
    import thread_utils
    import builtins
    import components.master_search as master_search
    import components.geofence_utils as geofence_utils

    def _log_req(method, url, **kwargs):

        def _debug_jwt(token_str):
            try:
                if not token_str or len(token_str) < 10:
                    return 'Invalid/Empty Token'
                if token_str.startswith('Bearer '):
                    token_str = token_str.replace('Bearer ', '')
                parts = token_str.split('.')
                if len(parts) < 2:
                    return 'Not a JWT'
                payload = parts[1]
                pad = len(payload) % 4
                if pad:
                    payload += '=' * (4 - pad)
                import base64
                decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
                claims = json.loads(decoded)
                user = claims.get('preferred_username') or claims.get('sub')
                iss = claims.get('iss', '')
                tenant = iss.split('/')[-1] if '/' in iss else 'Unknown'
                return f'User: {user} | Tenant: {tenant}'
            except Exception as e:
                return f'Decode Error: {e}'
        headers = kwargs.get('headers', {})
        auth_header = headers.get('Authorization', 'None')
        token_meta = _debug_jwt(auth_header)
        print(f'[API_DEBUG] ----------------------------------------------------------------')
        print(f'[API_DEBUG] 🚀 REQUEST: {method} {url}')
        print(f'[API_DEBUG] 🔑 TOKEN META: {token_meta}')
        payload = kwargs.get('json') or kwargs.get('data')
        if not payload:
            files = kwargs.get('files')
            if files and isinstance(files, dict):
                if 'dto' in files:
                    val = files['dto']
                    if isinstance(val, (list, tuple)) and len(val) > 1:
                        payload = f'[Multipart DTO] {val[1]}'
                    else:
                        payload = f'[Multipart DTO] {val}'
                else:
                    payload = f'[Multipart Files] Keys: {list(files.keys())}'
        if not payload:
            payload = 'No Payload'
        payload_type = 'JSON' if kwargs.get('json') else 'Data'
        if payload_type == 'Data' and isinstance(payload, str):
            try:
                json.loads(payload)
                payload_type = 'Data (JSON)'
            except:
                pass
        if not kwargs.get('json') and (not kwargs.get('data')) and (not payload_type == 'Data (JSON)'):
            payload_type = 'Unknown/Multipart'
        try:
            if method == 'GET':
                resp = requests.get(url, **kwargs)
            elif method == 'POST':
                resp = requests.post(url, **kwargs)
            elif method == 'PUT':
                resp = requests.put(url, **kwargs)
            elif method == 'DELETE':
                resp = requests.delete(url, **kwargs)
            else:
                resp = requests.request(method, url, **kwargs)
            body_preview = 'Binary/No Content'
            try:
                if not resp.text or not resp.text.strip():
                    body_preview = '[Empty Response]'
                else:
                    try:
                        json_obj = resp.json()
                        body_preview = json.dumps(json_obj, indent=2)
                    except:
                        body_preview = resp.text[:4000]
            except:
                pass
            status_icon = '✅' if 200 <= resp.status_code < 300 else '❌'
            print(f'[API_DEBUG] {status_icon} RESPONSE [{resp.status_code}]')
            print(f'[API_DEBUG] 📄 BODY:\n{body_preview}')
            print(f'[API_DEBUG] ----------------------------------------------------------------\n')
            return resp
        except Exception as e:
            print(f'[API_DEBUG] ❌ EXCEPTION: {e}')
            print(f'[API_DEBUG] ----------------------------------------------------------------\n')
            raise e

    def _log_get(url, **kwargs):
        return _log_req('GET', url, **kwargs)

    def _log_post(url, **kwargs):
        return _log_req('POST', url, **kwargs)

    def _log_put(url, **kwargs):
        return _log_req('PUT', url, **kwargs)

    def _log_delete(url, **kwargs):
        return _log_req('DELETE', url, **kwargs)

    def _safe_iloc(row, idx):
        try:
            if isinstance(row, dict):
                keys = list(row.keys())
                if 0 <= idx < len(keys):
                    val = row[keys[idx]]
                    return val.strip() if isinstance(val, str) else val
                return None
            elif isinstance(row, list):
                if 0 <= idx < len(row):
                    return row[idx]
                return None
            return row.iloc[idx]
        except:
            return None
    import sys
    sys.argv = [sys.argv[0]]
    builtins.data = data
    builtins.data_df = pd.DataFrame(data)
    import os
    valid_token_path = os.path.join(os.getcwd(), 'valid_token.txt')
    if os.path.exists(valid_token_path):
        try:
            with open(valid_token_path, 'r') as f:
                forced_token = f.read().strip()
            if len(forced_token) > 10:
                print(f'[API_DEBUG] ⚠️ OVERRIDE: Using token from valid_token.txt')
                token = forced_token
        except Exception:
            pass
    builtins.token = token
    builtins.base_url = env_config.get('apiBaseUrl')
    base_url = builtins.base_url
    env_key = env_config.get('environment')
    file_path = 'Uploaded_File.xlsx'
    builtins.file_path = file_path
    env_url = base_url
    builtins.env_url = base_url

    class MockCell:

        def __init__(self, row_data, key):
            self.row_data = row_data
            self.key = key

        @property
        def value(self):
            return self.row_data.get(self.key)

        @value.setter
        def value(self, val):
            self.row_data[self.key] = val

    class MockSheet:

        def __init__(self, data):
            self.data = data

        def cell(self, row, column, value=None):
            idx = row - 2
            if not 0 <= idx < len(self.data):
                return MockCell({}, 'dummy')
            row_data = self.data[idx]
            keys = list(row_data.keys())
            if 1 <= column <= len(keys):
                key = keys[column - 1]
            elif 'output_columns' in dir(builtins) and 0 <= column - 1 < len(builtins.output_columns):
                key = builtins.output_columns[column - 1]
            else:
                key = f'Column_{column}'
            cell = MockCell(row_data, key)
            if value is not None:
                cell.value = value
            return cell

        @property
        def max_row(self):
            return len(self.data) + 1

    class MockWorkbook:

        def __init__(self, data_or_builtins):
            if hasattr(data_or_builtins, 'data'):
                self.data = data_or_builtins.data
            else:
                self.data = data_or_builtins

        def __getitem__(self, key):
            return MockSheet(self.data)

        @property
        def sheetnames(self):
            return ['Sheet1', 'Environment_Details', 'Plot_details', 'Sheet']

        def save(self, path):
            import json
            print(f'[MOCK] Excel saved to {path}')
            try:
                print('[OUTPUT_DATA_DUMP]')
                print(json.dumps(self.data))
                print('[/OUTPUT_DATA_DUMP]')
            except:
                pass

        @property
        def active(self):
            return MockSheet(self.data)
    wk = MockWorkbook(builtins)
    builtins.wk = wk
    builtins.wb = wk
    wb = wk
    global _plottag_cache, _geocode_cache, _use_provided_tag_ids, _use_lat_lng_for_geo_method
    _plottag_cache = {}
    _geocode_cache = {}
    _use_lat_lng_for_geo_method = False
    _use_provided_tag_ids = False

    def _user_run(data, token, env_config):
        """
    Master function to orchestrate the processing of each row in parallel.
    Initializes global settings and dispatches rows to process_row.
    """
        builtins.token = token
        builtins.env_config = env_config
        global _use_lat_lng_for_geo_method
        global _use_provided_tag_ids
        _use_lat_lng_for_geo_method = False
        if data and len(data) > 0:
            first_row = data[0]
            if first_row.get('latitude') is not None and str(first_row.get('latitude')).strip() != '' and (first_row.get('longitude') is not None) and (str(first_row.get('longitude')).strip() != ''):
                _use_lat_lng_for_geo_method = True
            print(f'[GEO_INIT] Geo method determined: {('Latitude/Longitude' if _use_lat_lng_for_geo_method else 'Address')}')
            if first_row.get('tag_id') is not None and str(first_row.get('tag_id')).strip() != '':
                _use_provided_tag_ids = True
            print(f'[MASTER_INIT] Tag ID lookup method: {('Provided IDs' if _use_provided_tag_ids else 'Search by Name')}')
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)

    def process_row(row):
        """
    Processes a single row from the Excel input to create a place.
    Performs master data lookup, geocoding, and API call.
    """
        original_row = dict(row)
        row['Status'] = 'Fail'
        row['Response'] = ''
        row['tag_id'] = ''
        row['Name'] = original_row.get('name', '')
        place_name = original_row.get('name')
        place_type = original_row.get('type')
        if not place_name:
            row['Response'] = 'Place name is missing.'
            return row
        if not place_type:
            row['Response'] = 'Place type is missing.'
            return row
        tag_id = None
        tags_input = original_row.get('tags')
        if tags_input:
            if _use_provided_tag_ids:
                provided_tag_id = original_row.get('tag_id')
                if not provided_tag_id:
                    row['Response'] = 'Tag ID is empty (Strict Mode, expected in input).'
                    print(f'[PLTTAG_LOOKUP] {tags_input} → ID: Not Found (Empty in Strict Mode)')
                    return row
                try:
                    tag_id = int(provided_tag_id)
                except ValueError:
                    row['Response'] = 'Provided Tag ID is not a valid integer.'
                    print(f'[PLTTAG_LOOKUP] {tags_input} → ID: Not Found (Invalid format)')
                    return row
                print(f'[PLTTAG_LOOKUP] {tags_input} → ID: {tag_id} (Provided)')
            else:
                with _plottag_lock:
                    result = master_search.search('plottag', tags_input, builtins.env_config, _plottag_cache)
                if not result['found']:
                    row['Response'] = f'Tag not found: {result['message']}'
                    print(f'[PLTTAG_LOOKUP] {tags_input} → Result: Not Found')
                    return row
                tag_id = result['value']
                print(f'[PLTTAG_LOOKUP] {tags_input} → ID: {tag_id}')
        if tag_id:
            row['tag_id'] = str(tag_id)
        location_input = None
        lat_for_payload_root = None
        lng_for_payload_root = None
        place_address_payload = {}
        if _use_lat_lng_for_geo_method:
            latitude_val = original_row.get('latitude')
            longitude_val = original_row.get('longitude')
            if latitude_val is None or longitude_val is None or str(latitude_val).strip() == '' or (str(longitude_val).strip() == ''):
                row['Response'] = 'Latitude or Longitude is missing for this row (expected for all rows based on first row).'
                return row
            try:
                lat_for_payload_root = float(latitude_val)
                lng_for_payload_root = float(longitude_val)
            except ValueError:
                row['Response'] = 'Invalid Latitude or Longitude format.'
                return row
            location_input = f'{lat_for_payload_root},{lng_for_payload_root}'
        else:
            address_val = original_row.get('address')
            if not address_val:
                row['Response'] = 'Address is missing for this row (expected for all rows based on first row).'
                return row
            location_input = address_val
        with _geocode_lock:
            if location_input in _geocode_cache:
                address_component = _geocode_cache[location_input]
                print(f'[GEOFENCE] {location_input} → (Cached)')
            else:
                google_api_key = builtins.env_config.get('Geocoding_api_key')
                if not google_api_key:
                    row['Response'] = 'Google API key is missing in environment configuration for geocoding.'
                    return row
                geocode_result = geofence_utils.get_boundary(location_input, google_api_key)
                if not geocode_result:
                    row['Response'] = f'Geocoding failed for "{location_input}". No boundary data found.'
                    print(f'[GEOFENCE] {location_input} → Result: Geocoding Failed')
                    return row
                address_component = geofence_utils.parse_address_component(geocode_result)
                _geocode_cache[location_input] = address_component
                print(f'[GEOFENCE] {location_input} → lat={address_component.get('latitude', 'N/A'):.6f}, lng={address_component.get('longitude', 'N/A'):.6f}')
        place_address_payload = {'country': address_component.get('country'), 'formattedAddress': address_component.get('formattedAddress'), 'administrativeAreaLevel1': address_component.get('administrativeAreaLevel1'), 'locality': address_component.get('locality'), 'administrativeAreaLevel2': address_component.get('administrativeAreaLevel2'), 'sublocalityLevel1': address_component.get('sublocalityLevel1', ''), 'sublocalityLevel2': address_component.get('sublocalityLevel2', ''), 'landmark': address_component.get('landmark', ''), 'postalCode': address_component.get('postalCode', ''), 'houseNo': address_component.get('houseNo', ''), 'buildingName': address_component.get('buildingName', ''), 'placeId': address_component.get('placeId'), 'latitude': address_component.get('latitude'), 'longitude': address_component.get('longitude')}
        if not _use_lat_lng_for_geo_method:
            lat_for_payload_root = place_address_payload.get('latitude')
            lng_for_payload_root = place_address_payload.get('longitude')
            if lat_for_payload_root is None or lng_for_payload_root is None:
                row['Response'] = 'Geocoded address did not provide valid latitude/longitude for API payload.'
                return row
        api_url = f'{base_url}/services/farm/api/place'
        headers = {'Authorization': f'Bearer {builtins.token}', 'Content-Type': 'application/json'}
        place_data_attribute = {'tags': [int(tag_id)]} if tag_id else None
        payload = {'data': place_data_attribute, 'type': place_type.upper(), 'name': place_name, 'address': place_address_payload, 'latitude': lat_for_payload_root, 'longitude': lng_for_payload_root}
        try:
            response = _log_post(api_url, headers=headers, json=payload)
            if response.status_code in [200, 201]:
                row['Status'] = 'Pass'
                row['Response'] = 'Place added'
            else:
                row['Response'] = f'Place creation failed with status {response.status_code}: {response.text}'
        except requests.exceptions.HTTPError as e:
            row['Response'] = f'HTTP Error during place creation: {e.response.status_code} - {e.response.text}'
        except requests.exceptions.ConnectionError as e:
            row['Response'] = f'Connection Error during place creation: {e}'
        except requests.exceptions.Timeout as e:
            row['Response'] = f'Timeout Error during place creation: {e}'
        except requests.exceptions.RequestException as e:
            row['Response'] = f'An unexpected request error occurred during place creation: {e}'
        except Exception as e:
            row['Response'] = f'An unexpected error occurred: {e}'
        return row
    "\nOUTPUT MAPPING CONFIGURATION:\n- UI Output Definition:\n- UI Column 'Name': Set to '' (Logic: from excel)\n- UI Column 'Status': Set to '' (Logic: 'Fail' if tag not found or if status code of place creation is not 200 or 201\n'Pass' if status of place creation is 200 or 201)\n- Excel Output Definition:\n   - Column 'tag_id': Set to '' (Logic: attribute 'id' from tag API response)\n   - Column 'Status': Set to '' (Logic: 'Fail' if tag not found or if status code of place creation is not 200 or 201\n'Pass' if status of place creation is 200 or 201)\n   - Column 'Response': Set to '' (Logic: 'Tag not found' if tag not found or \nwhole response of place creation if status code is not 200 or 201\n'Place added' if place creation response code is 200 or 201)\n"
    _plottag_lock = thread_utils.create_lock()
    _geocode_lock = thread_utils.create_lock()
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
