def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import requests
    import json
    import concurrent.futures

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
            else:
                resp = requests.request(method, url, **kwargs)
            body_preview = 'Binary/No Content'
            try:
                if not resp.text:
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
        api_path = '/services/farm/api/croppable-areas/plot-risk/batch'
        url = f'{base_url}{api_path}'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        batch_size = 25
        indexed_data = []
        for i, row in enumerate(data):
            try:
                ca_id = row['croppableAreaId']
                f_id = row['farmerId']
                indexed_data.append({'croppableAreaId': ca_id, 'farmerId': f_id, '_original_row_index': i})
            except KeyError:
                row['Status'] = 'Input Error'
                row['API response'] = 'Missing required input column: croppableAreaId or farmerId.'
        for i in range(0, len(indexed_data), batch_size):
            batch = indexed_data[i:i + batch_size]
            if not batch:
                continue
            payload = []
            ca_id_map = {}
            for item in batch:
                ca_id = item['croppableAreaId']
                f_id = item['farmerId']
                index = item['_original_row_index']
                payload.append({'croppableAreaId': ca_id, 'farmerId': f_id})
                ca_id_map[str(ca_id)] = index
            try:
                print(f'[Log] Sending batch of {len(payload)} items...')
                response = _log_post(url, headers=headers, json=payload)
                status_code = response.status_code
                if status_code == 200:
                    try:
                        response_json = response.json()
                        sr_plot_details = response_json.get('srPlotDetails', {})
                        for ca_id_str, detail in sr_plot_details.items():
                            original_index = ca_id_map.get(ca_id_str)
                            if original_index is not None:
                                row = data[original_index]
                                item_status = detail.get('status', 'Unknown')
                                if item_status == 'SF_VALIDATION_FAILED' or item_status == 'Failed':
                                    row['Status'] = 'Failed'
                                else:
                                    row['Status'] = 'Success'
                                row['Code'] = status_code
                                message = detail.get('message', detail.get('error', f'No message found in details for CA {ca_id_str}'))
                                row['API response'] = message
                                sr_plot_id = detail.get('srPlotId')
                                if sr_plot_id:
                                    row['srPlotId'] = sr_plot_id
                    except json.JSONDecodeError:
                        error_msg = f'Request successful but failed to decode JSON response. Raw response snippet: {response.text[:200]}'
                        for original_index in ca_id_map.values():
                            row = data[original_index]
                            row['Status'] = 'Failed (JSON Error)'
                            row['Code'] = status_code
                            row['API response'] = error_msg
                else:
                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        response_data = response.text
                    error_response_str = json.dumps(response_data) if isinstance(response_data, dict) else str(response_data)
                    for original_index in ca_id_map.values():
                        row = data[original_index]
                        row['Status'] = 'Failed'
                        row['Code'] = status_code
                        row['API response'] = f'API Call Failed (Status {status_code}). Response: {error_response_str}'
            except requests.RequestException as e:
                error_msg = str(e)
                for original_index in ca_id_map.values():
                    row = data[original_index]
                    row['Status'] = 'Failed'
                    row['Code'] = 'Exception'
                    row['API response'] = f'Request Exception: {error_msg}'
                    row['Status'] = 'Failed'
                    row['Code'] = 'Exception'
                    row['API response'] = f'Request Exception: {error_msg}'
        import builtins
        if hasattr(builtins, 'data_df'):
            del builtins.data_df
        return data
    res = _user_run(data, token, env_config)
    try:
        if hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res