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
        """
    Executes the automation script to add an asset tag to assets from Excel data.

    Args:
        data (list of dict): A list of dictionaries, where each dictionary represents a row
                             from the Excel sheet. Expected keys: 'Asset Name', 'Asset ID',
                             'Tag', 'Tag ID', 'Status', 'API_Response'.
        token (str): The authorization token for API calls.
        env_config (dict): A dictionary containing environment-specific configurations,
                           including 'apiBaseUrl'.

    Returns:
        list of dict: The updated list of dictionaries with 'Status' and 'API_Response'
                      for each row.
    """
        cache = {'asset_tags': None}

        def process_row(row):
            """
        Processes a single row of Excel data to add an asset tag.

        Args:
            row (dict): A dictionary representing a single row from the Excel sheet.

        Returns:
            dict: The updated row dictionary with processing status and API response.
        """
            api_base_url = env_config['apiBaseUrl']
            headers = {'Authorization': f'Bearer {token}'}
            asset_tag_name = row.get('Tag')
            if not asset_tag_name:
                row['Status'] = 'Fail'
                row['API_Response'] = 'Excel column "Tag" is empty.'
                return row
            asset_tag_id = None
            asset_tags_list = cache['asset_tags']
            if asset_tags_list is None:
                asset_tags_url = f'{api_base_url}/services/master/api/filter'
                asset_tags_params = {'type': 'ASSET', 'size': 5000}
                try:
                    asset_tags_resp = _log_get(asset_tags_url, headers=headers, params=asset_tags_params)
                    asset_tags_resp.raise_for_status()
                    asset_tags_list = asset_tags_resp.json()
                    cache['asset_tags'] = asset_tags_list
                except requests.exceptions.RequestException as e:
                    row['Status'] = 'Fail'
                    row['API_Response'] = f'Step 1 API call (Asset Tag) failed: {e}'
                    return row
                except json.JSONDecodeError:
                    row['Status'] = 'Fail'
                    row['API_Response'] = f'Step 1 API (Asset Tag) returned invalid JSON: {asset_tags_resp.text}'
                    return row
            found_tag_data = None
            if asset_tags_list:
                for tag in asset_tags_list:
                    if tag.get('name') == asset_tag_name:
                        found_tag_data = tag
                        break
            if found_tag_data:
                asset_tag_id = found_tag_data.get('id')
                row['Tag ID'] = asset_tag_id
            else:
                row['Status'] = 'Fail'
                row['API_Response'] = 'Tag not Found'
                return row
            asset_id = row.get('Asset ID')
            if not asset_id:
                row['Status'] = 'Fail'
                row['API_Response'] = 'Excel column "Asset ID" is empty.'
                return row
            asset_details_url = f'{api_base_url}/services/farm/api/assets/{asset_id}'
            asset_details_response = None
            try:
                asset_details_resp = _log_get(asset_details_url, headers=headers)
                asset_details_resp.raise_for_status()
                asset_details_response = asset_details_resp.json()
                row['_asset_details_response'] = asset_details_response
            except requests.exceptions.RequestException as e:
                row['Status'] = 'Fail'
                row['API_Response'] = f'Step 2 API call (Asset Details) failed: {e}'
                return row
            except json.JSONDecodeError:
                row['Status'] = 'Fail'
                row['API_Response'] = f'Step 2 API (Asset Details) returned invalid JSON: {asset_details_resp.text}'
                return row
            if not asset_details_response:
                row['Status'] = 'Fail'
                row['API_Response'] = 'Asset not Found or empty response from Step 2 API.'
                return row
            asset_update_url = f'{api_base_url}/services/farm/api/assets'
            payload = row['_asset_details_response'].copy()
            if 'data' not in payload or payload['data'] is None:
                payload['data'] = {}
            elif not isinstance(payload['data'], dict):
                payload['data'] = {}
            if 'tags' not in payload['data'] or payload['data']['tags'] is None:
                payload['data']['tags'] = []
            elif not isinstance(payload['data']['tags'], list):
                payload['data']['tags'] = [payload['data']['tags']] if payload['data']['tags'] else []
            if asset_tag_id is not None and asset_tag_id not in payload['data']['tags']:
                payload['data']['tags'].append(asset_tag_id)
            payload = attribute_utils.add_attributes_to_payload(row, payload, env_config, target_key='data')
            update_headers = headers.copy()
            if 'Content-Type' in update_headers:
                del update_headers['Content-Type']
            files = {'dto': (None, json.dumps(payload), 'application/json')}
            try:
                asset_update_resp = _log_put(asset_update_url, headers=update_headers, files=files)
                asset_update_resp.raise_for_status()
                update_response_json = asset_update_resp.json()
                row['Status'] = 'Success'
                row['API_Response'] = json.dumps(update_response_json)
            except requests.exceptions.RequestException as e:
                row['Status'] = 'Fail'
                row['API_Response'] = f'Step 3 API call (Asset Update) failed: {e}'
            except json.JSONDecodeError:
                row['Status'] = 'Fail'
                row['API_Response'] = f'Step 3 API (Asset Update) returned invalid JSON: {asset_update_resp.text}'
            return row
        return thread_utils.run_in_parallel(process_row, data)
    return _user_run(data, token, env_config)
