# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = False
# EXPECTED_INPUT_COLUMNS: Asset Name, Asset ID, Tag Name, Tag ID, Status, Response

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

    def _user_run(data, token, env_config):
        """
    Main entry point for the script. Orchestrates the parallel processing.
    """
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)

    def process_row(row):
        """
    Processes a single row of data from the Excel sheet to add an asset tag.
    """
        row['Asset Name'] = row.get('Asset Name')
        row['Asset ID'] = row.get('Asset ID')
        row['Tag Name'] = row.get('Tag Name')
        row['Tag ID'] = ''
        row['Status'] = 'Fail'
        row['Response'] = ''
        asset_id = str(row.get('Asset ID', '')).strip()
        tag_name = str(row.get('Tag Name', '')).strip()
        if not asset_id:
            row['Response'] = 'Asset ID is empty.'
            print(f'[ERROR] Skipping row due to empty Asset ID.')
            return row
        if not tag_name:
            row['Response'] = 'Tag Name is empty.'
            print(f'[ERROR] Skipping row due to empty Tag Name for Asset ID: {asset_id}')
            return row
        print(f"[ASSETTAG_LOOKUP] Searching for Tag Name: '{tag_name}'")
        tag_lookup_result = master_search.lookup_from_cache(_assettag_list, 'name', tag_name, 'id')
        if not tag_lookup_result['found']:
            row['Response'] = tag_lookup_result['message']
            print(f'[ASSETTAG_LOOKUP] {tag_name} → ID: Not Found. Message: {tag_lookup_result['message']}')
            return row
        resolved_tag_id = tag_lookup_result['value']
        row['Tag ID'] = resolved_tag_id
        print(f'[ASSETTAG_LOOKUP] {tag_name} → ID: {resolved_tag_id}')
        headers = {'Authorization': f'Bearer {builtins.token}', 'Content-Type': 'application/json'}
        get_asset_url = f'{base_url}/services/farm/api/assets/{asset_id}'
        print(f'[API_CALL] Fetching Asset Details for Asset ID: {asset_id}')
        response = None
        try:
            response = _log_get(get_asset_url, headers=headers)
            response.raise_for_status()
            asset_data = response.json()
            print(f'[API_RESPONSE] Fetched Asset Details for {asset_id} successfully.')
        except requests.exceptions.RequestException as e:
            error_message = f'Failed to fetch asset details for Asset ID {asset_id}: {e}'
            if response is not None and hasattr(response, 'text'):
                error_message += f'. Response: {response.text}'
            row['Response'] = error_message
            print(f'[ERROR] {error_message}')
            return row
        except json.JSONDecodeError:
            error_message = f'Failed to decode JSON from asset details for Asset ID {asset_id}. Raw response: {response.text}'
            row['Response'] = error_message
            print(f'[ERROR] {error_message}')
            return row
        current_tags = asset_data.get('data', {}).get('tags', [])
        tag_added = False
        if resolved_tag_id not in current_tags:
            current_tags.append(resolved_tag_id)
            if 'data' not in asset_data or asset_data['data'] is None:
                asset_data['data'] = {}
            asset_data['data']['tags'] = current_tags
            tag_added = True
            print(f"[LOGIC] Tag ID {resolved_tag_id} added to asset {asset_id}'s tags list.")
        else:
            row['Status'] = 'Pass'
            row['Response'] = 'Tag already associated with asset'
            print(f'[LOGIC] Tag ID {resolved_tag_id} was already present for asset {asset_id}. No update needed.')
            return row
        if tag_added:
            put_asset_url = f'{base_url}/services/farm/api/assets'
            payload_data = asset_data
            files = {'dto': (None, json.dumps(payload_data), 'application/json')}
            print(f'[API_CALL] Updating Asset Tags for Asset ID: {asset_id}')
            try:
                response = _log_put(put_asset_url, headers={'Authorization': f'Bearer {builtins.token}'}, files=files)
                if response.status_code in [200, 201]:
                    row['Status'] = 'Pass'
                    row['Response'] = 'Tag updated to asset'
                    print(f'[API_RESPONSE] Successfully updated tags for Asset ID {asset_id}.')
                else:
                    row['Status'] = 'Fail'
                    row['Response'] = response.text
                    print(f'[ERROR] Failed to update tags for Asset ID {asset_id}. Status: {response.status_code}, Response: {response.text}')
                return row
            except requests.exceptions.RequestException as e:
                row['Status'] = 'Fail'
                row['Response'] = f'API request failed when updating asset {asset_id}: {e}'
                print(f'[ERROR] API request failed for asset {asset_id}: {e}')
                return row
        else:
            row['Status'] = 'Pass'
            row['Response'] = 'No new tag was added (already present or logic error).'
            print(f'[LOGIC] No update needed for asset {asset_id} as no new tag was flagged for addition.')
            return row
    _assettag_list = master_search.fetch_all('assettag', builtins.env_config)
    print(f'[ASSETTAG_MASTER] Fetched {len(_assettag_list)} asset tags during module load.')
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
