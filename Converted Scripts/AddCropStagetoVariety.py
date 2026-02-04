def run(data, token, env_config):
    import pandas as pd
    import builtins
    import concurrent.futures
    import requests
    import json
    import threading

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

    def _user_run(data, token, env_config):
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
            import copy
            import attribute_utils
            import json
            import os
            import sys
            print(f'DEBUG: Requests module: {requests.__file__}')

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
                        import json
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
                if not base_url:
                    raise ValueError('BASE_URL not found in env_config')
                cache = {'crop_map': None, 'stage_map': None}
                variety_cache = {}
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
                                key = str(crop['name']).strip().lower()
                                crop_map[key] = crop['id']
                        cache['crop_map'] = crop_map
                    except Exception as e:
                        print(f'Error fetching crop data: {e}')
                        cache['crop_map'] = {}

                def fetch_and_cache_crop_stages():
                    url = f'{base_url}/services/farm/api/crop-stages'
                    auth_header = {'Authorization': f'Bearer {token}'}
                    try:
                        response = _log_get(url, headers=auth_header)
                        response.raise_for_status()
                        stages = response.json()
                        stage_map = {}
                        for stage in stages:
                            if stage.get('name'):
                                key = str(stage['name']).strip().lower()
                                stage_map[key] = stage
                        cache['stage_map'] = stage_map
                    except Exception as e:
                        print(f'Error fetching crop stage data: {e}')
                        cache['stage_map'] = {}
                if cache['crop_map'] is None:
                    fetch_and_cache_crops()
                if cache['stage_map'] is None:
                    fetch_and_cache_crop_stages()
                stage_map = cache['stage_map']
                crop_map = cache['crop_map']
                if not crop_map:
                    raise Exception('Critical Error: Failed to fetch Crop Master Data. Check API connection or Token.')
                for row in data:
                    row['status'] = 'Pending'
                    row['API response'] = ''
                    stage_name = row.get('cropStagename')
                    if stage_name:
                        stage_template = stage_map.get(str(stage_name).strip().lower())
                        if stage_template:
                            stage_data = copy.deepcopy(stage_template)
                            days = attribute_utils.safe_cast(row.get('cropStagedaysAfterSowing'), int)
                            if days is not None:
                                stage_data['daysAfterSowing'] = days
                            row['cropstagedata'] = stage_data
                        else:
                            row['cropstagedata'] = 'Invalid Crop Stage'
                    else:
                        row['cropstagedata'] = None
                    crop_name = row.get('cropName')
                    if crop_name and crop_map:
                        lookup_key = str(crop_name).strip().lower()
                        crop_id = crop_map.get(lookup_key)
                        if crop_id is not None:
                            row['cropId'] = crop_id
                grouped_data = {}
                error_data = []
                for row in data:
                    variety_id = row.get('varietyID')
                    if variety_id:
                        variety_id_str = str(variety_id)
                        if variety_id_str not in grouped_data:
                            grouped_data[variety_id_str] = []
                        grouped_data[variety_id_str].append(row)
                    else:
                        row['status'] = 'Failed'
                        row['API response'] = 'Missing required column: varietyID'
                        error_data.append(row)

                def fetch_variety_details(variety_id):
                    if variety_id in variety_cache:
                        return variety_cache[variety_id]
                    url = f'{base_url}/services/farm/api/varieties/{variety_id}'
                    headers = {'Authorization': f'Bearer {token}'}
                    try:
                        response = _log_get(url, headers=headers)
                        if response.status_code == 404:
                            return 'Variety not found'
                        response.raise_for_status()
                        details = response.json()
                        variety_cache[variety_id] = details
                        return details
                    except Exception as e:
                        return f'API Error fetching Variety {variety_id}: {str(e)}'

                def process_group(item):
                    variety_id, rows = item
                    variety_data = fetch_variety_details(variety_id)
                    if isinstance(variety_data, str):
                        error_msg = variety_data
                        for row in rows:
                            row['status'] = 'Failed'
                            row['API response'] = error_msg
                        return rows
                    payload = copy.deepcopy(variety_data)
                    existing_stages_map = {stage.get('id'): stage for stage in payload.get('cropStages', []) if stage.get('id') is not None}
                    stages_to_add = {}
                    for row in rows:
                        stage_data = row.get('cropstagedata')
                        if not isinstance(stage_data, dict):
                            continue
                        new_stage_id = stage_data.get('id')
                        if new_stage_id is not None and new_stage_id in existing_stages_map:
                            existing_stage = existing_stages_map[new_stage_id]
                            new_days = stage_data.get('daysAfterSowing')
                            existing_days = existing_stage.get('daysAfterSowing')
                            if new_days != existing_days:
                                existing_stage['daysAfterSowing'] = new_days
                        elif new_stage_id is not None and new_stage_id not in existing_stages_map:
                            if new_stage_id not in stages_to_add:
                                stages_to_add[new_stage_id] = stage_data
                        elif new_stage_id is None:
                            stage_key = stage_data.get('name')
                            if stage_key and stage_key not in stages_to_add:
                                stages_to_add[stage_key] = stage_data
                    final_stages_list = list(existing_stages_map.values()) + list(stages_to_add.values())
                    payload['cropStages'] = final_stages_list
                    if not payload.get('cropId') and rows[0].get('cropId'):
                        payload['cropId'] = rows[0].get('cropId')
                    try:
                        url = f'{base_url}/services/farm/api/varieties'
                        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                        response = _log_put(url, headers=headers, json=payload)
                        if response.status_code == 400:
                            try:
                                error_resp = response.json()
                                error_msg = error_resp.get('title', f'400 Bad Request: Error title not found. {response.text[:100]}')
                            except requests.exceptions.JSONDecodeError:
                                error_msg = f'400 Bad Request, JSON parsing failed. Content: {response.text[:100]}'
                            for row in rows:
                                row['status'] = 'Failed'
                                row['API response'] = error_msg
                            return rows
                        response.raise_for_status()
                        api_resp = response.json()
                        status_msg = f'Successfully updated Variety ID: {variety_id}'
                        variety_cache[variety_id] = api_resp
                        for row in rows:
                            row['status'] = 'Success'
                            row['API response'] = status_msg
                    except Exception as e:
                        error_msg = str(e)
                        for row in rows:
                            row['status'] = 'Failed'
                            row['API response'] = error_msg
                    return rows
                group_list = list(grouped_data.items())
                results_groups = []
                for item in group_list:
                    results_groups.append(process_group(item))
                final_data = error_data
                for group_rows in results_groups:
                    final_data.extend(group_rows)
                return final_data
            return _user_run(data, token, env_config)
        return _user_run(data, token, env_config)
    return _user_run(data, token, env_config)
