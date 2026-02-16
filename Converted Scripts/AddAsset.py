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
        print(f'[API_DEBUG] 📦 PAYLOAD ({payload_type}): {payload}')
        print(f'[API_DEBUG] ----------------------------------------------------------------')
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
    global _geocode_cache, _farmer_cache, _soiltype_list, _irrigationtype_list
    _farmer_cache = {}
    _geocode_cache = {}
    _soiltype_list = None
    _irrigationtype_list = None

    def _user_run(data, token, env_config):
        """
    Main entry point for the script. Initializes common resources and delegates
    row processing to `process_row` in parallel.
    """
        builtins.token = token
        builtins.env_config = env_config
        global _soiltype_list
        global _irrigationtype_list
        with _lock:
            if _soiltype_list is None:
                _soiltype_list = master_search.fetch_all('soiltype', builtins.env_config)
                print(f'[MASTER_INIT] Soil Type master data fetched. Count: {(len(_soiltype_list) if _soiltype_list else 0)}')
            if _irrigationtype_list is None:
                _irrigationtype_list = master_search.fetch_all('irrigationtype', builtins.env_config)
                print(f'[MASTER_INIT] Irrigation Type master data fetched. Count: {(len(_irrigationtype_list) if _irrigationtype_list else 0)}')
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)

    def process_row(row):
        """
    Processes a single row of data from the Excel sheet.
    Performs master data lookups, geocoding, and calls the Asset creation API.
    """
        row['Status'] = 'Fail'
        row['Asset ID'] = 'NA'
        row['Response'] = ''
        row['Asset Name'] = row.get('Asset Name', '')
        farmer_name = row.get('Farmer Name')
        if not farmer_name:
            row['Response'] = 'Farmer Name is missing.'
            return row
        with _lock:
            farmer_result = master_search.search('farmer', farmer_name, builtins.env_config, _farmer_cache)
        print(f'[FARMER_LOOKUP] {farmer_name} -> ID: {(farmer_result['value'] if farmer_result['found'] else 'Not Found')}')
        if not farmer_result['found']:
            row['Response'] = farmer_result['message']
            return row
        row['Farmer Name_id'] = farmer_result['value']
        soil_type_name = row.get('Soil Type')
        if not soil_type_name:
            row['Response'] = 'Soil Type is missing.'
            return row
        soil_type_result = master_search.lookup_from_cache(_soiltype_list, 'name', soil_type_name, 'id')
        print(f'[SOILTYPE_LOOKUP] {soil_type_name} -> ID: {(soil_type_result['value'] if soil_type_result['found'] else 'Not Found')}')
        if not soil_type_result['found']:
            row['Response'] = soil_type_result['message']
            return row
        row['Soil Type_id'] = soil_type_result['value']
        irrigation_type_name = row.get('Irrigation Type')
        if not irrigation_type_name:
            row['Response'] = 'Irrigation Type is missing.'
            return row
        irrigation_type_result = master_search.lookup_from_cache(_irrigationtype_list, 'name', irrigation_type_name, 'id')
        print(f'[IRRIGATIONTYPE_LOOKUP] {irrigation_type_name} -> ID: {(irrigation_type_result['value'] if irrigation_type_result['found'] else 'Not Found')}')
        if not irrigation_type_result['found']:
            row['Response'] = irrigation_type_result['message']
            return row
        row['Irrigation Type_id'] = irrigation_type_result['value']
        address = row.get('Address')
        address_component_payload = None
        if address:
            with _lock:
                if address in _geocode_cache:
                    address_component = _geocode_cache[address]
                    print(f'[GEOFENCE_CACHE] {address} -> Using cached result.')
                else:
                    google_api_key = builtins.env_config.get('Geocoding_api_key')
                    if not google_api_key:
                        row['Response'] = 'Geocoding API key not configured in environment.'
                        return row
                    geocode_result = geofence_utils.get_boundary(address, google_api_key)
                    if geocode_result:
                        address_component = geofence_utils.parse_address_component(geocode_result)
                        _geocode_cache[address] = address_component
                        print(f'[GEOFENCE] {address} -> lat={address_component.get('latitude', 'N/A')}, lng={address_component.get('longitude', 'N/A')}')
                    else:
                        row['Response'] = f'Failed to geocode address: "{address}"'
                        return row
            address_component_payload = {'country': address_component.get('country'), 'formattedAddress': address_component.get('formattedAddress'), 'administrativeAreaLevel1': address_component.get('administrativeAreaLevel1'), 'locality': address_component.get('locality'), 'administrativeAreaLevel2': address_component.get('administrativeAreaLevel2'), 'sublocalityLevel1': address_component.get('sublocalityLevel1'), 'sublocalityLevel2': address_component.get('sublocalityLevel2'), 'landmark': address_component.get('landmark'), 'postalCode': address_component.get('postalCode'), 'houseNo': address_component.get('houseNo'), 'buildingName': address_component.get('buildingName'), 'placeId': address_component.get('placeId'), 'latitude': address_component.get('latitude'), 'longitude': address_component.get('longitude')}
            row['Address Component (non mandatory)'] = json.dumps(address_component_payload)
        else:
            row['Response'] = 'Address column is missing for geocoding.'
            return row
        asset_creation_url = f'{base_url}/services/farm/api/assets'
        declared_area_raw = row.get('Declared Area')
        try:
            declared_area_count = float(declared_area_raw)
        except (ValueError, TypeError):
            row['Response'] = 'Invalid Declared Area. Must be a numeric value.'
            return row
        payload = {'declaredArea': {'count': declared_area_count}, 'name': row.get('Asset Name'), 'ownerId': row['Farmer Name_id'], 'soilType': {'id': row['Soil Type_id']}, 'irrigationType': {'id': row['Irrigation Type_id']}, 'address': address_component_payload}
        files = {'dto': (None, json.dumps(payload), 'application/json')}
        api_headers = {'Authorization': f'Bearer {builtins.token}'}
        try:
            response = _log_post(asset_creation_url, headers=api_headers, files=files)
            response_json = {}
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                pass
            if response.status_code in [200, 201]:
                row['Status'] = 'Pass'
                asset_id = response_json.get('id')
                row['Asset ID'] = asset_id
                row['Response'] = 'Asset Created Successfully'
            else:
                row['Status'] = 'Fail'
                if response.status_code == 400:
                    row['Response'] = response_json.get('title', f'Bad Request: {response.text}')
                else:
                    row['Response'] = f'API Error: {response.status_code} - {response_json.get('message', response.text)}'
                row['Asset ID'] = 'NA'
        except requests.exceptions.HTTPError as e:
            row['Status'] = 'Fail'
            error_response_json = {}
            try:
                if e.response:
                    error_response_json = e.response.json()
            except json.JSONDecodeError:
                pass
            row['Response'] = f'HTTP Error: {e.response.status_code} - {error_response_json.get('message', e.response.text if e.response else str(e))}'
            row['Asset ID'] = 'NA'
        except requests.exceptions.ConnectionError as e:
            row['Status'] = 'Fail'
            row['Response'] = f'Network Error: Could not connect to API - {e}'
            row['Asset ID'] = 'NA'
        except requests.exceptions.Timeout as e:
            row['Status'] = 'Fail'
            row['Response'] = f'Request Timeout: API did not respond in time - {e}'
            row['Asset ID'] = 'NA'
        except Exception as e:
            row['Status'] = 'Fail'
            row['Response'] = f'An unexpected error occurred: {e}'
            row['Asset ID'] = 'NA'
        return row
    _lock = thread_utils.create_lock()
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
