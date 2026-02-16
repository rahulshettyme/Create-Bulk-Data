# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = True
# EXPECTED_INPUT_COLUMNS: Farmer Name, Farmer Code, Phone Number, AssignedTo, UserID, Address, Address Component (non mandatory), Status, Farmer ID, Response

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
    global _user_cache, _use_provided_user_ids, _geocode_cache
    _geocode_cache = {}
    _user_cache = {}
    _use_provided_user_ids = False

    def _user_run(data, token, env_config):
        """
    Main function to orchestrate the processing of farmer data.
    """
        builtins.token = token
        builtins.env_config = env_config
        global _use_provided_user_ids
        _use_provided_user_ids = bool(data and data[0].get('UserID'))
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)

    def process_row(row):
        """
    Processes a single row of farmer data from the Excel sheet.
    """
        row['Status'] = 'Fail'
        row['Response'] = 'Processing started'
        row['Farmer ID'] = 'NA'
        farmer_name_ui = row.get('Farmer Name', '')
        address_input = row.get('Address', '').strip()
        address_component_payload = {}
        if not address_input:
            row['Response'] = 'Address is empty'
            return row
        with _geocode_lock:
            if address_input in _geocode_cache:
                address_component = _geocode_cache[address_input]
                print(f'[GEOFENCE] {address_input} (cached) → lat={address_component.get('latitude', 'N/A'):.6f}, lng={address_component.get('longitude', 'N/A'):.6f}')
            else:
                try:
                    geocode_result = geofence_utils.get_boundary(address_input, builtins.env_config.get('Geocoding_api_key'))
                    if not geocode_result:
                        row['Response'] = f'Geocoding failed for address: {address_input}'
                        print(f'[GEOFENCE] {address_input} → Result: Not Found')
                        return row
                    address_component = geofence_utils.parse_address_component(geocode_result)
                    _geocode_cache[address_input] = address_component
                    print(f'[GEOFENCE] {address_input} → lat={address_component.get('latitude', 'N/A'):.6f}, lng={address_component.get('longitude', 'N/A'):.6f}')
                except Exception as e:
                    row['Response'] = f'Error during geocoding: {str(e)}'
                    print(f'[GEOFENCE] {address_input} → Error: {str(e)}')
                    return row
        address_component_output_payload = {'id': None, 'formattedAddress': address_component.get('formattedAddress'), 'postalCode': address_component.get('postalCode'), 'locality': address_component.get('locality'), 'data': None, 'administrativeAreaLevel5': address_component.get('administrativeAreaLevel5'), 'administrativeAreaLevel4': address_component.get('administrativeAreaLevel4'), 'administrativeAreaLevel3': address_component.get('administrativeAreaLevel3'), 'administrativeAreaLevel2': address_component.get('administrativeAreaLevel2'), 'administrativeAreaLevel1': address_component.get('administrativeAreaLevel1'), 'country': address_component.get('country'), 'latitude': address_component.get('latitude'), 'longitude': address_component.get('longitude'), 'placeId': address_component.get('placeId'), 'sublocalityLevel1': address_component.get('sublocalityLevel1', ''), 'sublocalityLevel2': address_component.get('sublocalityLevel2', ''), 'sublocalityLevel3': address_component.get('sublocalityLevel3'), 'sublocalityLevel4': address_component.get('sublocalityLevel4'), 'sublocalityLevel5': address_component.get('sublocalityLevel5'), 'houseNo': address_component.get('houseNo', ''), 'buildingName': address_component.get('buildingName', ''), 'landmark': address_component.get('landmark', ''), 'clientId': builtins.env_config.get('clientId', None)}
        for key in ['sublocalityLevel1', 'sublocalityLevel2', 'houseNo', 'buildingName', 'landmark']:
            if address_component_output_payload.get(key) is None:
                address_component_output_payload[key] = ''
        for key in ['id', 'data', 'administrativeAreaLevel5', 'administrativeAreaLevel4', 'administrativeAreaLevel3', 'sublocalityLevel3', 'sublocalityLevel4', 'sublocalityLevel5', 'clientId']:
            if address_component_output_payload.get(key) is None:
                address_component_output_payload[key] = None
        row['Address Component (non mandatory)'] = json.dumps(address_component_output_payload)
        assigned_to_name = row.get('AssignedTo', '').strip()
        user_id = None
        if not assigned_to_name:
            row['Response'] = 'AssignedTo name is empty'
            return row
        if _use_provided_user_ids:
            user_id = row.get('UserID')
            if not user_id:
                row['Status'] = 'Fail'
                row['Response'] = 'UserID is empty (Strict Mode)'
                print(f'[USER_LOOKUP] {assigned_to_name} → ID: Not Found (Empty in Strict Mode)')
                return row
            print(f'[USER_LOOKUP] {assigned_to_name} → ID: {user_id} (Provided)')
        else:
            user_result = master_search.search('user', assigned_to_name, builtins.env_config, _user_cache)
            if not user_result['found']:
                row['Status'] = 'Fail'
                row['Response'] = user_result['message']
                print(f'[USER_LOOKUP] {assigned_to_name} → ID: Not Found')
                return row
            user_id = user_result['value']
            print(f'[USER_LOOKUP] {assigned_to_name} → ID: {user_id}')
        row['UserID'] = user_id
        phone_raw = str(row.get('Phone Number', '')).strip()
        farmer_first_name = row.get('Farmer Name', '').strip()
        farmer_code = row.get('Farmer Code', '').strip()
        if ' ' in phone_raw:
            parts = phone_raw.split(' ')
        elif '-' in phone_raw:
            parts = phone_raw.split('-')
        else:
            row['Status'] = 'Fail'
            row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
            return row
        if len(parts) != 2:
            row['Status'] = 'Fail'
            row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
            return row
        country_code = '+' + parts[0]
        mobile_number = parts[1]
        address_payload_for_api = {'country': address_component.get('country'), 'formattedAddress': address_component.get('formattedAddress'), 'houseNo': address_component.get('houseNo', ''), 'buildingName': address_component.get('buildingName', ''), 'administrativeAreaLevel1': address_component.get('administrativeAreaLevel1'), 'locality': address_component.get('locality'), 'administrativeAreaLevel2': address_component.get('administrativeAreaLevel2'), 'sublocalityLevel1': address_component.get('sublocalityLevel1', ''), 'sublocalityLevel2': address_component.get('sublocalityLevel2', ''), 'landmark': address_component.get('landmark', ''), 'postalCode': address_component.get('postalCode'), 'placeId': address_component.get('placeId'), 'latitude': address_component.get('latitude'), 'longitude': address_component.get('longitude')}
        for key in ['houseNo', 'buildingName', 'sublocalityLevel1', 'sublocalityLevel2', 'landmark']:
            if address_payload_for_api.get(key) is None:
                address_payload_for_api[key] = ''
        payload = {'data': {'mobileNumber': mobile_number, 'countryCode': country_code}, 'firstName': farmer_first_name, 'farmerCode': farmer_code, 'assignedTo': [{'id': user_id, 'name': assigned_to_name}], 'address': address_payload_for_api}
        api_url = f'{builtins.env_config.get('apiBaseUrl')}/services/farm/api/farmers'
        headers = {'Authorization': f'Bearer {builtins.token}'}
        files = {'dto': (None, json.dumps(payload), 'application/json')}
        try:
            response = _log_post(api_url, headers=headers, files=files)
            response_json = response.json() if response.content else {}
            if response.ok:
                row['Status'] = 'Pass'
                row['Farmer ID'] = response_json.get('id', 'NA')
                row['Response'] = 'Farmer Created Successfully'
            else:
                row['Status'] = 'Fail'
                row['Farmer ID'] = 'NA'
                if response.status_code == 400:
                    error_key = response_json.get('errorKey', f'Bad Request ({response.status_code})')
                    row['Response'] = error_key
                else:
                    row['Response'] = f'API Error ({response.status_code}): {response_json.get('message', 'Unknown error')}'
        except requests.exceptions.RequestException as e:
            row['Status'] = 'Fail'
            row['Response'] = f'Network or API request error: {str(e)}'
        except json.JSONDecodeError:
            row['Status'] = 'Fail'
            row['Response'] = f'API did not return valid JSON. Status: {response.status_code}, Response: {response.text}'
        except Exception as e:
            row['Status'] = 'Fail'
            row['Response'] = f'An unexpected error occurred: {str(e)}'
        row['Farmer Name'] = farmer_name_ui
        return row
    _geocode_lock = thread_utils.create_lock()
    _user_lock = thread_utils.create_lock()
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
