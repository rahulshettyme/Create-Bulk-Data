def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import json
    import requests
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
        print(f'[API_DEBUG] 📦 PAYLOAD: {payload}')
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

    def _user_run(data, token, env_config):
        """
    Main function to process location data from Excel-like input and retrieve
    geographical boundary information using a geofencing utility.

    Args:
        data (list of dict): A list of dictionaries, where each dictionary represents a row
                             and must contain a 'Location' key.
        token (str): An authentication token (not directly used by this specific script logic).
        env_config (dict): A dictionary containing environment-specific configurations,
                           including the 'google_api_key'.

    Returns:
        list of dict: The input data list with the 'Output' column populated with
                      JSON strings representing the geocoded boundary information
                      or an error/null state.
    """
        results = []
        for row in data:
            processed_row = row.copy()
            location_name = processed_row.get('Location')
            output_payload = None
            if location_name:
                google_api_key = env_config.get('Geocoding_api_key')
                if not google_api_key:
                    output_payload = {'error': 'Google API Key missing in environment configuration.'}
                else:
                    try:
                        boundary_data = geofence_utils.get_boundary(location_name, google_api_key)
                        if boundary_data and isinstance(boundary_data, dict) and boundary_data.get('place_id'):
                            output_payload = {}

                            def get_component_long_name(components, component_type):
                                for comp in components:
                                    if component_type in comp.get('types', []):
                                        return comp.get('long_name')
                                return None
                            if 'geometry' in boundary_data:
                                if 'bounds' in boundary_data['geometry']:
                                    output_payload['bounds'] = boundary_data['geometry']['bounds']
                                elif 'viewport' in boundary_data['geometry']:
                                    output_payload['bounds'] = boundary_data['geometry']['viewport']
                            address_components = boundary_data.get('address_components', [])
                            output_payload['country'] = get_component_long_name(address_components, 'country')
                            output_payload['administrativeAreaLevel1'] = get_component_long_name(address_components, 'administrative_area_level_1')
                            output_payload['administrativeAreaLevel2'] = get_component_long_name(address_components, 'administrative_area_level_2')
                            output_payload['administrativeAreaLevel3'] = get_component_long_name(address_components, 'administrative_area_level_3')
                            output_payload['placeId'] = boundary_data.get('place_id')
                            if 'geometry' in boundary_data and 'location' in boundary_data['geometry']:
                                output_payload['latitude'] = boundary_data['geometry']['location'].get('lat')
                                output_payload['longitude'] = boundary_data['geometry']['location'].get('lng')
                            if 'geojson_polygon' in boundary_data:
                                output_payload['geoInfo'] = boundary_data['geojson_polygon']
                            else:
                                output_payload['geoInfo'] = {'type': 'FeatureCollection', 'features': []}
                            name_value = None
                            name_value = get_component_long_name(address_components, 'locality')
                            if not name_value:
                                name_value = get_component_long_name(address_components, 'sublocality_level_1')
                            if not name_value:
                                formatted_address = boundary_data.get('formatted_address')
                                if formatted_address:
                                    name_value = formatted_address.split(',')[0].strip()
                            if not name_value:
                                name_value = location_name
                            output_payload['name'] = name_value
                        else:
                            output_payload = None
                    except Exception as e:
                        output_payload = {'error': f"Error processing location '{location_name}': {str(e)}"}
            else:
                output_payload = None
            processed_row['Output'] = json.dumps(output_payload)
            results.append(processed_row)
        return results
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
