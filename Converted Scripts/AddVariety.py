def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import thread_utils
    import attribute_utils

    def _log_req(method, url, **kwargs):
        import requests
        import json

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
        payload = kwargs.get('json') or kwargs.get('data') or 'No Payload'
        print(f'[API_DEBUG] 📦 PAYLOAD: {payload}')
        print(f'[API_DEBUG] ----------------------------------------------------------------')
        try:
            if method == 'GET':
                resp = requests.get(url, **kwargs)
            elif method == 'POST':
                resp = requests.post(url, **kwargs)
            elif method == 'PUT':
                resp = requests.put(url, **kwargs)
            else:
                resp = requests.request(method, url, **kwargs)
            try:
                body_preview = resp.text[:1000].replace('\n', ' ').replace('\r', '')
            except:
                body_preview = 'Binary/No Content'
            status_icon = '✅' if 200 <= resp.status_code < 300 else '❌'
            print(f'[API_DEBUG] {status_icon} RESPONSE [{resp.status_code}]')
            print(f'[API_DEBUG] 📄 BODY: {body_preview}')
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
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        cache = {'crop_map': None}
        locations = {'bounds': {'northeast': {'lat': 72.7087158, 'lng': -66.3193754}, 'southwest': {'lat': 15.7760139, 'lng': -173.2992296}}, 'country': 'United States', 'placeId': 'ChIJCzYy5IS16lQRQrfeQ5K5Oxw', 'latitude': 38.7945952, 'longitude': -106.5348379, 'geoInfo': {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Polygon', 'coordinates': [[[-173.2992296, 15.7760139], [-66.3193754, 15.7760139], [-66.3193754, 72.7087158], [-173.2992296, 72.7087158], [-173.2992296, 15.7760139]]]}}]}, 'name': 'United States'}

        def fetch_and_cache_crops():
            url = f'{base_url}/services/farm/api/crops?size=1000'
            auth_header = {'Authorization': f'Bearer {token}'}
            try:
                response = _log_get(url, headers=auth_header)
                response.raise_for_status()
                crops = response.json()
                crop_map = {}
                for crop in crops:
                    if crop.get('name') and crop.get('id'):
                        crop_map[crop['name'].lower()] = crop['id']
                cache['crop_map'] = crop_map
            except Exception as e:
                print(f'Error fetching crop data (Step 1): {e}')
                cache['crop_map'] = {}
        if cache['crop_map'] is None:
            fetch_and_cache_crops()

        def process_row(row):
            row['status'] = 'Pending'
            row['API response'] = ''
            crop_map = cache['crop_map']
            crop_name = row.get('cropName')
            if not crop_name:
                row['status'] = 'Failed'
                row['API response'] = 'Missing required column: cropName'
                return row
            crop_id = crop_map.get(str(crop_name).lower())
            if crop_id is None:
                row['status'] = 'Failed'
                row['API response'] = f"Crop name '{crop_name}' not found in master data."
                row['cropId'] = None
                return row
            row['cropId'] = crop_id
            try:
                expected_yield_value = attribute_utils.safe_cast(row.get('expectedYield'), float)
                expected_harvest_days_value = attribute_utils.safe_cast(row.get('expectedHarvestDays'), int)
                payload = {'data': {'yieldPerLocation': [{'data': {}, 'locations': locations, 'expectedYield': expected_yield_value, 'expectedYieldQuantity': '', 'expectedYieldUnits': row.get('expectedYieldUnits'), 'refrenceAreaUnits': row.get('refrenceAreaUnits')}]}, 'cropId': crop_id, 'name': row.get('name'), 'nickName': row.get('nickName'), 'expectedHarvestDays': expected_harvest_days_value, 'processStandardDeduction': None, 'cropPrice': None, 'cropStages': [], 'seedGrades': [], 'harvestGrades': [], 'id': None, 'varietyAdditionalAttributeList': []}
                payload = attribute_utils.add_attributes_to_payload(row, payload, env_config, target_key='data')
                url = f'{base_url}/services/farm/api/varieties'
                response = _log_post(url, headers=headers, json=payload)
                response.raise_for_status()
                api_response = response.json()
                row['status'] = 'Success'
                row['API response'] = json.dumps(api_response)
            except requests.exceptions.RequestException as e:
                status_code = e.response.status_code if e.response is not None else 'N/A'
                error_text = e.response.text if e.response is not None else str(e)
                row['status'] = f'Failed (HTTP {status_code})'
                row['API response'] = error_text
            except Exception as e:
                row['status'] = 'Failed (Processing Error)'
                row['API response'] = str(e)
            return row
        return thread_utils.run_in_parallel(process_row, data)
    return _user_run(data, token, env_config)
