def run(data, token, env_config):
    import builtins
    import concurrent.futures
    import requests
    import json
    import json
    import pandas as pd
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

    def safe_int(value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def post_data_to_api(get_api_url, put_api_url, token, input_file, output_file, dto=None):
        print(f'\n[INFO] Loading data from Excel: {input_file}')
        exdata = builtins.data_df
        print('[INFO] Cleaning data: Replacing NaN values with empty strings')
        exdata = exdata.fillna('')
        print('[INFO] Adding status tracking columns')
        exdata['status'] = ''
        exdata['Response'] = ''
        print(f'\n[INFO] Starting to process {len(exdata)} rows from the Excel file')
        for index, row in exdata.iterrows():
            print(f'\n[ROW {index + 1}] Processing row')
            try:
                croppable_area_id = _safe_iloc(row, 0)
                plan_name = _safe_iloc(row, 1)
                plantype_id = _safe_iloc(row, 2)
                plan_type_name = _safe_iloc(row, 3)
                project_id = _safe_iloc(row, 4)
                varieties = _safe_iloc(row, 5)
                schedule_type = _safe_iloc(row, 6)
                no_of_days = safe_int(_safe_iloc(row, 7))
                execute_when = _safe_iloc(row, 8)
                reference_date = _safe_iloc(row, 9)
                required_days = safe_int(_safe_iloc(row, 10))
                print(f'[ROW {index + 1}] Sending GET request for Plan Type ID: {plantype_id}')
                get_url = f'{get_api_url}/{plantype_id}'
                headers = {'Authorization': f'Bearer {token}'}
                get_response = _log_get(get_url, headers=headers)
                if get_response.status_code == 200:
                    print(f'[ROW {index + 1}] GET request successful.')
                    plantype_response = get_response.json()
                else:
                    print(f'[ROW {index + 1}] GET request failed with status: {get_response.status_code}')
                    exdata.at[index, 'status'] = f'Failed GET: {get_response.status_code}'
                    continue
                print(f'[ROW {index + 1}] Preparing payload for POST request')
                post_payload = {'croppableAreaId': croppable_area_id, 'data': {'information': {'planName': plan_name, 'planType': plantype_response, 'geoLocation': False, 'signature': False}, 'customAttributes': {}, 'planHeaderAttributes': [], 'planHeaderGroup': {}}, 'images': {}, 'name': plan_name, 'planTypeId': plantype_id, 'planTypeName': plan_type_name, 'projectId': project_id, 'schedule': {'planParams': f'?croppableAreaIds={croppable_area_id}', 'type': schedule_type, 'fixedDate': False, 'noOfDays': no_of_days, 'executeWhen': execute_when, 'referenceDate': reference_date, 'requiredDays': required_days, 'recuring': False}, 'varieties': [varieties]}
                multipart_data = {'dto': (None, json.dumps(post_payload), 'application/json')}
                print(f'[ROW {index + 1}] Sending POST request to {put_api_url}/{croppable_area_id}')
                post_response = _log_post(f'{put_api_url}/{croppable_area_id}', headers=headers, files=multipart_data)
                if post_response.status_code == 200:
                    print(f'[ROW {index + 1}] POST request successful')
                    exdata.at[index, 'status'] = 'Success'
                    exdata.at[index, 'Response'] = f'Code: {post_response.status_code}, Message: {post_response.text}'
                else:
                    print(f'[ROW {index + 1}] POST request failed, Status: {post_response.status_code}')
                    exdata.at[index, 'status'] = f'Failed POST: {post_response.status_code}'
                    exdata.at[index, 'Response'] = f'Reason: {post_response.reason}, Message: {post_response.text}'
                print(f'[ROW {index + 1}] Waiting for 0.3 seconds before continuing...')
                time.sleep(0.3)
            except Exception as e:
                print(f'[ROW {index + 1}] ❌ Error: {str(e)}')
                exdata.at[index, 'status'] = f'Error: {str(e)}'
        print(f'\n[INFO] Saving results to output Excel: {output_file}')
        exdata.to_excel(output_file, index=False)
        print('[INFO] Process completed successfully.')
    if True:
        print('\n========== PLAN API AUTOMATION SCRIPT STARTED ==========')
        get_api_url = 'https://cloud.cropin.in/services/farm/api/plan-types'
        put_api_url = 'https://cloud.cropin.in/services/farm/api/plans/non-pops/ca'
        input_excel = 'C:\\Users\\rajasekhar.palleti\\Downloads\\API_Plan_Template.xlsx'
        output_excel = 'C:\\Users\\rajasekhar.palleti\\Downloads\\API_Plan_Template_output.xlsx'
        tenant_code = 'asp'
        print('[INFO] Requesting access token for tenant:', tenant_code)
        if token:
            print('[INFO] Access token retrieved successfully ✅')
            post_data_to_api(get_api_url, put_api_url, token, input_excel, output_excel)
        else:
            print('[ERROR] Failed to retrieve access token. ❌ Process terminated.')
        print('========== SCRIPT FINISHED ==========\n')
    return data
