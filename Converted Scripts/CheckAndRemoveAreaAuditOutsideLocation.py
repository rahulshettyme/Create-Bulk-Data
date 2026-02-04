def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json

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
        import pandas as pd
        import builtins
        import requests
        import json
        import threading
        import thread_utils
        import geofence_utils
        import sys
        import os

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
                return _safe_iloc(row, idx)
            except:
                return None
        sys.argv = [sys.argv[0]]
        builtins.data = data
        builtins.data_df = pd.DataFrame(data)
        valid_token_path = os.path.join(os.getcwd(), 'valid_token.txt')
        if os.path.exists(valid_token_path):
            try:
                with open(valid_token_path, 'r') as f:
                    forced_token = f.read().strip()
                if len(forced_token) > 10:
                    pass
            except Exception:
                pass
        builtins.token = token
        builtins.base_url = env_config.get('apiBaseUrl')
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
                try:
                    pass
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
            target_location = env_config.get('targetLocation')
            google_api_key = env_config.get('google_api_key')
            geo_cache = {}
            for row in data:
                row.setdefault('is_outside_location', '')
                row.setdefault('area_audit_status', '')
                row.setdefault('area_audit_api_response', '')
                row.setdefault('CA_Name', '')
                try:
                    lat = float(str(row.get('Latitude', '')).strip())
                    lon = float(str(row.get('Longitude', '')).strip())
                    _loc_name, is_inside = geofence_utils.check_geofence(lat, lon, target_location, google_api_key, cache=geo_cache)
                    row['is_outside_location'] = 'NO' if is_inside else 'YES'
                except (ValueError, TypeError):
                    row['is_outside_location'] = 'INVALID_COORD'

            def process_row_for_api_and_output(row):
                ca_id = row.get('CA_ID')
                ui_status = 'Skipped'
                ui_response = 'N/A'
                if row.get('is_outside_location') == 'YES' and ca_id:
                    api_path = f'/services/farm/api/croppable-areas/{ca_id}/area-audit'
                    url = f'{base_url}{api_path}'
                    headers = {'Authorization': f'Bearer {token}'}
                    response_json = {}
                    http_status_code = None
                    crop_audited = None
                    try:
                        response = _log_delete(url, headers=headers)
                        http_status_code = response.status_code
                        try:
                            if response.text:
                                response_json = response.json()
                                crop_audited = response_json.get('cropAudited', None)
                        except json.JSONDecodeError:
                            pass
                        if crop_audited is False:
                            row['area_audit_status'] = 'Success'
                            row['area_audit_api_response'] = 'cropAudited = false'
                            ui_status = 'Success'
                            ui_response = 'cropAudited = false'
                        elif crop_audited is True:
                            row['area_audit_status'] = 'Fail'
                            row['area_audit_api_response'] = 'cropAudited = true'
                            ui_status = 'Fail'
                            ui_response = 'cropAudited = true'
                        elif http_status_code in (200, 204):
                            row['area_audit_status'] = 'Fail (API Response Issue)'
                            ui_status = 'Fail'
                            api_response_detail = f"HTTP Status: {http_status_code} | Expected 'cropAudited' field missing or invalid."
                            if response_json.get('message'):
                                api_response_detail += f' Message: {response_json.get('message')}'
                            elif response.text:
                                api_response_detail += f' Response Body: {response.text[:100]}...'
                            row['area_audit_api_response'] = api_response_detail
                            ui_response = api_response_detail
                        else:
                            row['area_audit_status'] = f'Fail (HTTP {http_status_code})'
                            ui_status = 'Fail'
                            api_response_detail = f'HTTP Status: {http_status_code}'
                            if response_json.get('message'):
                                api_response_detail += f' | Message: {response_json.get('message')}'
                            elif response_json.get('title'):
                                api_response_detail += f' | Title: {response_json.get('title')}'
                            elif response.text and (not response_json):
                                api_response_detail += f' | Response Body: {response.text[:100]}...'
                            row['area_audit_api_response'] = api_response_detail
                            ui_response = api_response_detail
                    except requests.exceptions.RequestException as e:
                        row['area_audit_status'] = 'Fail (Request Error)'
                        row['area_audit_api_response'] = str(e)
                        ui_status = 'Fail'
                        ui_response = str(e)
                else:
                    if row.get('is_outside_location') == 'NO':
                        row['area_audit_status'] = 'Skipped (Inside Location)'
                    elif row.get('is_outside_location') == 'INVALID_COORD':
                        row['area_audit_status'] = 'Skipped (Invalid Coordinates)'
                    elif not ca_id:
                        row['area_audit_status'] = 'Skipped (Missing CA_ID)'
                    row['area_audit_api_response'] = 'N/A'
                    ui_status = 'Skipped'
                    ui_response = 'N/A'
                row['ID'] = row.get('CA_ID')
                row['Name'] = row.get('CA_Name')
                row['Status'] = ui_status
                row['Response'] = ui_response
                return row
            processed_results = thread_utils.run_in_parallel(process_row_for_api_and_output, data)
            final_ui_output = []
            for row in processed_results:
                final_ui_output.append({'ID': row.get('ID'), 'Name': row.get('Name'), 'Status': row.get('Status'), 'Response': row.get('Response')})
            return final_ui_output
        res = _user_run(data, token, env_config)
        try:
            if res is None and hasattr(builtins, 'data_df'):
                if isinstance(builtins.data_df, pd.DataFrame):
                    res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
        except Exception as e:
            pass
        return res
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
