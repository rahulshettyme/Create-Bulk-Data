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
    import components.geofence_utils as geofence_utils
    import components.master_search as master_search

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
    _geocode_cache = {}
    _user_cache = {}

    def process_row(row):
        row['Status'] = 'Fail'
        row['Response'] = ''
        row['UserID'] = 'NA'
        row['Farmer ID'] = 'NA'
        address = row.get('Address')
        address_component_payload = None
        if not address:
            row['Response'] = 'Address is mandatory for geocoding.'
            print(f'[GEOFENCE] No Address provided for row. Skipping geocoding.')
            return row
        if address in _geocode_cache:
            address_component = _geocode_cache[address]
            print(f'[GEOFENCE] {address} → Cached Result. lat={address_component.get('latitude')}, lng={address_component.get('longitude')}')
        else:
            google_api_key = builtins.env_config.get('Geocoding_api_key')
            geocode_result = geofence_utils.get_boundary(address, google_api_key)
            if geocode_result:
                address_component = geofence_utils.parse_address_component(geocode_result)
                _geocode_cache[address] = address_component
                print(f'[GEOFENCE] {address} → lat={address_component.get('latitude')}, lng={address_component.get('longitude')}')
            else:
                row['Response'] = f'Geocoding failed for address: {address}'
                print(f'[GEOFENCE] {address} → Geocoding Failed.')
                return row
        address_component_payload = {'formattedAddress': address_component.get('formattedAddress'), 'postalCode': address_component.get('postalCode'), 'locality': address_component.get('locality'), 'administrativeAreaLevel2': address_component.get('administrativeAreaLevel2'), 'administrativeAreaLevel1': address_component.get('administrativeAreaLevel1'), 'country': address_component.get('country'), 'latitude': address_component.get('latitude'), 'longitude': address_component.get('longitude'), 'placeId': address_component.get('placeId'), 'sublocalityLevel1': address_component.get('sublocalityLevel1'), 'sublocalityLevel2': address_component.get('sublocalityLevel2'), 'houseNo': address_component.get('houseNo'), 'buildingName': address_component.get('buildingName'), 'landmark': address_component.get('landmark')}
        row['Address Component (non mandatory)'] = json.dumps(address_component_payload)
        assigned_to_name = row.get('AssignedTo')
        if not assigned_to_name:
            row['Response'] = 'AssignedTo is mandatory for farmer creation.'
            print(f'[USER_LOOKUP] AssignedTo missing → Skipping lookup.')
            return row
        user_lookup_result = master_search.search('user', assigned_to_name, builtins.env_config, _user_cache)
        if not user_lookup_result['found']:
            row['Response'] = user_lookup_result['message']
            print(f'[USER_LOOKUP] {assigned_to_name} → Result: {user_lookup_result['message']}')
            return row
        user_id = user_lookup_result['value']
        row['UserID'] = user_id
        print(f'[USER_LOOKUP] {assigned_to_name} → ID: {user_id}')
        phone_raw = str(row.get('Phone Number', '')).strip()
        if ' ' in phone_raw:
            parts = phone_raw.split(' ')
        elif '-' in phone_raw:
            parts = phone_raw.split('-')
        else:
            row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
            return row
        if len(parts) != 2:
            row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
            return row
        country_code = '+' + parts[0] if not parts[0].startswith('+') else parts[0]
        mobile_number = parts[1]
        payload = {'data': {'mobileNumber': mobile_number, 'countryCode': country_code}, 'firstName': row.get('Farmer Name'), 'farmerCode': row.get('Farmer Code'), 'assignedTo': [{'id': row['UserID'], 'name': row.get('AssignedTo')}], 'address': address_component_payload}
        url = f'{base_url}/services/farm/api/farmers'
        headers = {'Authorization': f'Bearer {builtins.token}'}
        try:
            files = {'dto': (None, json.dumps(payload), 'application/json')}
            response = _log_post(url, headers=headers, files=files)
            if response.ok:
                farmer_data = response.json()
                row['Status'] = 'Pass'
                row['Response'] = 'Farmer Created Successfully'
                row['Farmer ID'] = farmer_data.get('id', 'NA')
            else:
                row['Status'] = 'Fail'
                row['Farmer ID'] = 'NA'
                try:
                    error_data = response.json()
                    if response.status_code == 400 and 'title' in error_data:
                        row['Response'] = error_data['title']
                    else:
                        row['Response'] = error_data.get('message', str(error_data))
                except json.JSONDecodeError:
                    row['Response'] = response.text
        except requests.exceptions.RequestException as e:
            row['Status'] = 'Fail'
            row['Response'] = f'API request failed: {e}'
            row['Farmer ID'] = 'NA'
        return row

    def _user_run(data, token, env_config):
        builtins.token = token
        builtins.env_config = env_config
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
