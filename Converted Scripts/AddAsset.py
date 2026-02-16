# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = True
# EXPECTED_INPUT_COLUMNS: Asset Name, Farmer Name, Farmer_ID, Soil Type, Irrigation Type, Address, Declared Area

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
    global _soiltype_list, _use_provided_farmer_ids, _geocode_cache, _farmer_cache, _irrigationtype_list
    _farmer_cache = {}
    _soiltype_list = []
    _irrigationtype_list = []
    _geocode_cache = {}
    _use_provided_farmer_ids = False

    def _user_run(data, token, env_config):
        """
    Main function to orchestrate the asset creation process.
    Initializes builtins, master data caches, and orchestrates parallel processing.
    """
        builtins.token = token
        builtins.env_config = env_config
        global _soiltype_list, _irrigationtype_list, _use_provided_farmer_ids
        print("[MASTER_SEARCH] Fetching all 'soiltype' master data...")
        _soiltype_list = master_search.fetch_all('soiltype', env_config)
        print(f'[MASTER_SEARCH] Fetched {len(_soiltype_list)} soil types.')
        print("[MASTER_SEARCH] Fetching all 'irrigationtype' master data...")
        _irrigationtype_list = master_search.fetch_all('irrigationtype', env_config)
        print(f'[MASTER_SEARCH] Fetched {len(_irrigationtype_list)} irrigation types.')
        _use_provided_farmer_ids = bool(data and data[0].get('Farmer_ID'))
        if _use_provided_farmer_ids:
            print("[MASTER_SEARCH] 'Farmer_ID' column found in input. Using provided IDs for farmer lookup.")
        else:
            print("[MASTER_SEARCH] 'Farmer_ID' column not found or empty. Performing farmer search API calls.")
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)

    def process_row(row):
        """
    Processes a single row of data from the Excel sheet to create an asset.
    Handles master data lookups, geocoding, and the final API call.
    """
        row['Status'] = 'Fail'
        row['Asset ID'] = 'NA'
        row['Response'] = ''
        asset_name = row.get('Asset Name')
        farmer_name = row.get('Farmer Name')
        soil_type_name = row.get('Soil Type')
        irrigation_type_name = row.get('Irrigation Type')
        address_raw = row.get('Address')
        declared_area_str = str(row.get('Declared Area')).strip()
        if not asset_name:
            row['Response'] = 'Asset Name is missing.'
            print(f'[ERROR] Skipping row - Asset Name is missing.')
            return row
        if not farmer_name and (not _use_provided_farmer_ids):
            row['Response'] = 'Farmer Name is missing (and Farmer_ID not provided).'
            print(f"[ERROR] Skipping row for asset '{asset_name}' - Farmer Name is missing.")
            return row
        if not soil_type_name:
            row['Response'] = 'Soil Type is missing.'
            print(f"[ERROR] Skipping row for asset '{asset_name}' - Soil Type is missing.")
            return row
        if not irrigation_type_name:
            row['Response'] = 'Irrigation Type is missing.'
            print(f"[ERROR] Skipping row for asset '{asset_name}' - Irrigation Type is missing.")
            return row
        if not address_raw:
            row['Response'] = 'Address is missing.'
            print(f"[ERROR] Skipping row for asset '{asset_name}' - Address is missing.")
            return row
        declared_area = None
        try:
            if declared_area_str:
                declared_area = float(declared_area_str)
            else:
                row['Response'] = 'Declared Area is empty.'
                print(f"[ERROR] Skipping row for asset '{asset_name}' - Declared Area is empty.")
                return row
        except ValueError:
            row['Response'] = f"Invalid format for Declared Area: '{declared_area_str}'."
            print(f"[ERROR] Skipping row for asset '{asset_name}' - Invalid Declared Area.")
            return row
        farmer_id = None
        if _use_provided_farmer_ids:
            farmer_id = row.get('Farmer_ID')
            if not farmer_id:
                row['Response'] = 'Farmer_ID is empty (Strict Mode: expected ID in column).'
                print(f'[FARMER_LOOKUP] {farmer_name} → ID: Not Found (Empty in Strict Mode)')
                return row
            print(f'[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id} (Provided)')
        else:
            with _farmer_cache_lock:
                farmer_lookup_result = master_search.search('farmer', farmer_name, builtins.env_config, _farmer_cache)
            if not farmer_lookup_result['found']:
                row['Response'] = f'Farmer not found: {farmer_lookup_result['message']}'
                print(f'[FARMER_LOOKUP] {farmer_name} → Result: Not Found')
                return row
            farmer_id = farmer_lookup_result['value']
            row['Farmer_ID'] = farmer_id
            print(f'[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id}')
        soil_type_id = None
        soil_type_lookup_result = master_search.lookup_from_cache(_soiltype_list, 'name', soil_type_name, 'id')
        if not soil_type_lookup_result['found']:
            row['Response'] = f'Soil Type not found: {soil_type_lookup_result['message']}'
            print(f'[SOILTYPE_LOOKUP] {soil_type_name} → Result: Not Found')
            return row
        soil_type_id = soil_type_lookup_result['value']
        row['Soil Type_id'] = soil_type_id
        print(f'[SOILTYPE_LOOKUP] {soil_type_name} → ID: {soil_type_id}')
        irrigation_type_id = None
        irrigation_type_lookup_result = master_search.lookup_from_cache(_irrigationtype_list, 'name', irrigation_type_name, 'id')
        if not irrigation_type_lookup_result['found']:
            row['Response'] = f'Irrigation Type not found: {irrigation_type_lookup_result['message']}'
            print(f'[IRRIGATIONTYPE_LOOKUP] {irrigation_type_name} → Result: Not Found')
            return row
        irrigation_type_id = irrigation_type_lookup_result['value']
        row['Irrigation Type_id'] = irrigation_type_id
        print(f'[IRRIGATIONTYPE_LOOKUP] {irrigation_type_name} → ID: {irrigation_type_id}')
        address_component_payload = None
        with _geocode_cache_lock:
            if address_raw in _geocode_cache:
                address_component_payload = _geocode_cache[address_raw]
                lat_log_summary = f'lat={address_component_payload.get('latitude', 'N/A'):.6f}, lng={address_component_payload.get('longitude', 'N/A'):.6f}'
                print(f'[GEOFENCE] {address_raw} → Cache Hit. {lat_log_summary}')
            else:
                google_api_key = builtins.env_config.get('Geocoding_api_key')
                if not google_api_key:
                    row['Response'] = 'Geocoding API key is missing in environment configuration.'
                    print(f"[ERROR] Skipping row for asset '{asset_name}' - Geocoding API key missing.")
                    return row
                geocode_result = geofence_utils.get_boundary(address_raw, google_api_key)
                if not geocode_result:
                    row['Response'] = f"Geocoding failed for address: '{address_raw}'"
                    print(f'[GEOFENCE] {address_raw} → Result: Geocoding Failed')
                    return row
                parsed_address = geofence_utils.parse_address_component(geocode_result)
                address_component_payload = {'formattedAddress': parsed_address.get('formattedAddress'), 'postalCode': parsed_address.get('postalCode'), 'locality': parsed_address.get('locality'), 'data': None, 'administrativeAreaLevel5': parsed_address.get('administrativeAreaLevel5'), 'administrativeAreaLevel4': parsed_address.get('administrativeAreaLevel4'), 'administrativeAreaLevel3': parsed_address.get('administrativeAreaLevel3'), 'administrativeAreaLevel2': parsed_address.get('administrativeAreaLevel2'), 'administrativeAreaLevel1': parsed_address.get('administrativeAreaLevel1'), 'country': parsed_address.get('country'), 'latitude': parsed_address.get('latitude'), 'longitude': parsed_address.get('longitude'), 'placeId': parsed_address.get('placeId'), 'sublocalityLevel1': parsed_address.get('sublocalityLevel1'), 'sublocalityLevel2': parsed_address.get('sublocalityLevel2'), 'sublocalityLevel3': parsed_address.get('sublocalityLevel3'), 'sublocalityLevel4': parsed_address.get('sublocalityLevel4'), 'sublocalityLevel5': parsed_address.get('sublocalityLevel5'), 'houseNo': parsed_address.get('houseNo'), 'buildingName': parsed_address.get('buildingName'), 'landmark': parsed_address.get('landmark')}
                _geocode_cache[address_raw] = address_component_payload
                lat_log_summary = f'lat={address_component_payload.get('latitude', 'N/A'):.6f}, lng={address_component_payload.get('longitude', 'N/A'):.6f}'
                print(f'[GEOFENCE] {address_raw} → {lat_log_summary}')
        row['Address Component (non mandatory)'] = json.dumps(address_component_payload)
        api_url = f'{base_url}/services/farm/api/assets'
        headers = {'Authorization': f'Bearer {builtins.token}'}
        payload = {'declaredArea': {'count': declared_area}, 'name': asset_name, 'ownerId': farmer_id, 'soilType': {'id': soil_type_id}, 'irrigationType': {'id': irrigation_type_id}, 'address': address_component_payload}
        files = {'dto': (None, json.dumps(payload), 'application/json')}
        try:
            response = _log_post(api_url, headers=headers, files=files)
            response.raise_for_status()
            response_json = response.json()
            if response.status_code in [200, 201]:
                asset_id = response_json.get('id')
                row['Status'] = 'Pass'
                row['Asset ID'] = asset_id
                row['Response'] = 'Asset Created Successfully'
                print(f"[API] Asset '{asset_name}' created successfully. ID: {asset_id}")
            else:
                row['Response'] = f'Asset creation failed with unexpected status {response.status_code}: {response.text}'
                print(f"[API] Asset '{asset_name}' creation failed. Status: {response.status_code}, Response: {response.text}")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_message = e.response.text
            row['Asset ID'] = 'NA'
            if status_code == 400:
                try:
                    error_json = e.response.json()
                    error_title = error_json.get('title', error_message)
                    row['Response'] = error_title
                except json.JSONDecodeError:
                    row['Response'] = f'Asset creation failed (400 Bad Request): {error_message}'
            else:
                row['Response'] = f'Asset creation failed (HTTP Error {status_code}): {error_message}'
            print(f"[API] Asset '{asset_name}' creation failed. HTTP Status: {status_code}, Error: {row['Response']}")
        except requests.exceptions.RequestException as e:
            row['Response'] = f'Network or request error during asset creation: {e}'
            row['Asset ID'] = 'NA'
            print(f"[API] Asset '{asset_name}' creation failed. Request Exception: {e}")
        except Exception as e:
            row['Response'] = f'An unexpected error occurred: {e}'
            row['Asset ID'] = 'NA'
            print(f"[API] Asset '{asset_name}' creation failed. Unexpected Error: {e}")
        return row
    _farmer_cache_lock = thread_utils.create_lock()
    _geocode_cache_lock = thread_utils.create_lock()
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
