def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import json
    import requests
    import time

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

    def _user_run(rows, token, env_config):
        processed_rows = []
        if not base_url:
            env_name = env_config.get('environment', 'Prod')
            ENV_MAP = {'QA1': 'https://qa1.cropin.in', 'QA2': 'https://qa2.cropin.in', 'Prod': ''}
        headers = {'Authorization': f'Bearer {token}'}
        tag_map = {}
        try:
            resp = _log_get(f'{base_url}/services/master/api/filter?type=FARMER', headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get('data', [])
                for t in items:
                    tag_map[t.get('name', '').strip().lower()] = t.get('id')
            else:
                pass
        except Exception as e:
            pass
        farmer_api_base_url = f'{base_url}/services/farm/api/farmers'
        for row in rows:
            new_row = row.copy()
            new_row['Tag ID'] = ''
            new_row['Status'] = ''
            new_row['Response'] = ''
            try:
                f_name = str(row.get('Farmer Name') or '').strip()
                f_id_raw = str(row.get('Farmer ID') or '').strip()
                tag_name = str(row.get('Tag Name') or '').strip()
                new_row['Farmer Name'] = f_name
                new_row['Farmer ID'] = f_id_raw
                new_row['Tag Name'] = tag_name
                if not f_id_raw:
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = 'Missing Farmer ID'
                    processed_rows.append(new_row)
                    continue
                if not tag_name:
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = 'Missing Tag Name'
                    processed_rows.append(new_row)
                    continue
                tag_id = tag_map.get(tag_name.lower())
                if not tag_id:
                    new_row['Tag ID'] = ''
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = 'Tag not found'
                    processed_rows.append(new_row)
                    continue
                new_row['Tag ID'] = tag_id
                farmer_details_url = f'{farmer_api_base_url}/{f_id_raw}'
                f_resp = _log_get(farmer_details_url, headers=headers)
                if f_resp.status_code != 200:
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = f"Failed to fetch farmer details for ID '{f_id_raw}'. Status Code: {f_resp.status_code}, Response: {f_resp.text}"
                    processed_rows.append(new_row)
                    continue
                farmer_data = f_resp.json()
                if not farmer_data:
                    new_row['Status'] = 'Fail'
                    new_row['Response'] = 'Empty Farmer Data received from API when fetching details.'
                    processed_rows.append(new_row)
                    continue
                if 'data' not in farmer_data:
                    farmer_data['data'] = {}
                current_tags = farmer_data['data'].get('tags', [])
                tag_ids_on_farmer = []
                if isinstance(current_tags, list):
                    for t in current_tags:
                        try:
                            tag_ids_on_farmer.append(int(t))
                        except (ValueError, TypeError):
                            pass
                tag_needs_update = False
                if tag_id not in tag_ids_on_farmer:
                    tag_ids_on_farmer.append(tag_id)
                    farmer_data['data']['tags'] = tag_ids_on_farmer
                    tag_needs_update = True
                    files = {'dto': ('body.json', json.dumps(farmer_data), 'application/json')}
                    put_resp = _log_put(farmer_api_base_url, headers=headers, files=files)
                    if put_resp.status_code == 200:
                        new_row['Status'] = 'Pass'
                        new_row['Response'] = 'Tag updated to farmer'
                    else:
                        new_row['Status'] = 'Fail'
                        new_row['Response'] = put_resp.text
                else:
                    new_row['Status'] = 'Pass'
                    new_row['Response'] = f"Tag '{tag_name}' (ID: {tag_id}) already exists on farmer."
            except Exception as e:
                new_row['Status'] = 'Fail'
                new_row['Response'] = str(e)
            processed_rows.append(new_row)
        return processed_rows
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
