# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = False
# EXPECTED_INPUT_COLUMNS: Farmer Name, Farmer ID, Tag Name, Tag ID, Status, Response

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
    global _tag_master_cache, _use_provided_farmer_ids
    _tag_master_cache = {}
    _use_provided_farmer_ids = False

    def _fetch_master_tags(env_config):
        """
    Fetches master tags of type 'FARMER' and caches them.
    This function is called once if the cache is empty.
    """
        global _tag_master_cache
        url = f'{base_url}/services/master/api/filter'
        params = {'type': 'FARMER'}
        headers = {'Authorization': f'Bearer {builtins.token}', 'Content-Type': 'application/json'}
        try:
            response = _log_get(url, headers=headers, params=params)
            response.raise_for_status()
            tags_data = response.json()
            with _lock:
                if not _tag_master_cache:
                    for tag in tags_data:
                        _tag_master_cache[tag.get('name')] = tag.get('id')
                    print(f'[MASTER_TAGS] Fetched {len(_tag_master_cache)} FARMER tags.')
            return True
        except requests.exceptions.RequestException as e:
            print(f'[MASTER_TAGS_ERROR] Failed to fetch master tags: {e}')
            return False

    def process_row(row):
        """
    Processes a single row from the Excel input to add a tag to a farmer.
    """
        headers = {'Authorization': f'Bearer {builtins.token}', 'Content-Type': 'application/json'}
        row['Farmer Name'] = row.get('Farmer Name', '')
        row['Farmer ID'] = row.get('Farmer ID', '')
        row['Tag Name'] = row.get('Tag Name', '')
        row['Tag ID'] = ''
        row['Status'] = 'Fail'
        row['Response'] = 'Processing started.'
        farmer_name = row.get('Farmer Name')
        farmer_id = row.get('Farmer ID')
        tag_name = row.get('Tag Name')
        if not farmer_id:
            row['Response'] = 'Farmer ID is missing.'
            print(f'[ERROR] Skipping row for Farmer Name: {farmer_name} - Farmer ID is missing.')
            return row
        if not tag_name:
            row['Response'] = 'Tag Name is missing.'
            print(f'[ERROR] Skipping row for Farmer ID: {farmer_id} - Tag Name is missing.')
            return row
        with _lock:
            if not _tag_master_cache:
                if not _fetch_master_tags(builtins.env_config):
                    row['Response'] = 'Failed to fetch master tags during initialization.'
                    return row
        resolved_tag_id = _tag_master_cache.get(tag_name)
        if resolved_tag_id is None:
            row['Tag ID'] = ''
            row['Status'] = 'Fail'
            row['Response'] = 'Tag not found'
            print(f"[MASTER_TAG_LOOKUP] Tag Name: '{tag_name}' → ID: Not Found. Skipping row execution.")
            return row
        else:
            row['Tag ID'] = resolved_tag_id
            print(f"[MASTER_TAG_LOOKUP] Tag Name: '{tag_name}' → ID: {resolved_tag_id}")
        fetch_farmer_url = f'{base_url}/services/farm/api/farmers/{farmer_id}'
        try:
            farmer_resp = _log_get(fetch_farmer_url, headers=headers)
            if not farmer_resp.ok:
                row['Response'] = f'Failed to fetch farmer details (Status: {farmer_resp.status_code}): {farmer_resp.text}'
                row['Status'] = 'Fail'
                print(f'[FARMER_FETCH] Farmer ID: {farmer_id} → Status: Fail ({farmer_resp.status_code})')
                return row
            farmer_data = farmer_resp.json()
            print(f'[FARMER_FETCH] Farmer ID: {farmer_id} → Details fetched successfully.')
        except requests.exceptions.RequestException as e:
            row['Response'] = f'Error fetching farmer details for ID {farmer_id}: {e}'
            row['Status'] = 'Fail'
            print(f'[FARMER_FETCH_ERROR] Farmer ID: {farmer_id} → Error: {e}')
            return row
        if 'data' not in farmer_data or not isinstance(farmer_data['data'], dict):
            farmer_data['data'] = {}
        current_tags = farmer_data['data'].get('tags', [])
        if not isinstance(current_tags, list):
            current_tags = []
        original_tags_set = set(current_tags)
        updated_tags_set = set(current_tags)
        if resolved_tag_id not in updated_tags_set:
            updated_tags_set.add(resolved_tag_id)
            tag_added = True
        else:
            tag_added = False
        updated_tags_list = sorted(list(updated_tags_set))
        print(f'[LOGIC] Farmer ID: {farmer_id}. Original tags: {list(original_tags_set)}. Proposed tags: {updated_tags_list}.')
        if tag_added:
            update_payload = {'data': {'tags': updated_tags_list}}
            files = {'dto': (None, json.dumps(update_payload), 'application/json')}
            update_farmer_url = f'{base_url}/services/farm/api/farmers'
            try:
                update_resp = _log_put(update_farmer_url, headers={'Authorization': f'Bearer {builtins.token}'}, files=files)
                if update_resp.status_code in [200, 201]:
                    row['Status'] = 'Pass'
                    row['Response'] = 'Tag updated to farmer'
                    print(f'[FARMER_UPDATE] Farmer ID: {farmer_id} → Status: Pass ({update_resp.status_code})')
                else:
                    row['Status'] = 'Fail'
                    row['Response'] = f'Failed to update farmer tags (Status: {update_resp.status_code}): {update_resp.text}'
                    print(f'[FARMER_UPDATE] Farmer ID: {farmer_id} → Status: Fail ({update_resp.status_code})')
            except requests.exceptions.RequestException as e:
                row['Status'] = 'Fail'
                row['Response'] = f'Error updating farmer tags for ID {farmer_id}: {e}'
                print(f'[FARMER_UPDATE_ERROR] Farmer ID: {farmer_id} → Error: {e}')
        else:
            row['Status'] = 'Pass'
            row['Response'] = 'Tag already present for farmer'
            print(f"[FARMER_UPDATE] Farmer ID: {farmer_id} → Tag '{tag_name}' already present. No update needed.")
        return row

    def _user_run(data, token, env_config):
        """
    Main function to orchestrate the parallel processing of rows.
    """
        builtins.token = token
        builtins.env_config = env_config
        global _use_provided_farmer_ids
        _use_provided_farmer_ids = bool(data and data[0].get('Farmer ID'))
        with _lock:
            if not _tag_master_cache:
                if not _fetch_master_tags(env_config):
                    print('[ERROR] Script cannot proceed: Master tags could not be fetched.')
                    pass
        return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)
    _lock = thread_utils.create_lock()
    res = _user_run(data, token, env_config)
    try:
        if res is None and hasattr(builtins, 'data_df'):
            import pandas as pd
            if isinstance(builtins.data_df, pd.DataFrame):
                res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
    except Exception as e:
        print(f'[Warn] Failed to sync data_df to result: {e}')
    return res
