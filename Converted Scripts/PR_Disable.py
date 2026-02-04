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
        import builtins
        import concurrent.futures
        import requests
        import json
        import os
        import time
        import argparse
        from datetime import datetime
        import requests
        import pandas as pd

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
                return _safe_iloc(row, idx)
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
        sheet_name = 'Plot_details'
        env_sheet_name = 'Environment_Details'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        env_url = base_url
        env_url = base_url
        DELETE_PLOT_API = f'{env_url}/services/farm/api/intelligence/croppable-areas/request'
        STATUS_CHECK_API = f'{env_url}/services/farm/api/intelligence/croppable-areas/request/status?requestId={{}}'
        df = builtins.data_df

        def save_df_to_excel(df_to_save, file_path, sheet_name=None, max_retries=3):
            if sheet_name is None:
                sheet_name = sheet_name
            attempt = 0
            while attempt < max_retries:
                try:
                    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                        df_to_save.to_excel(writer, sheet_name, index=False)
                    print(f'✅ Excel updated: {file_path} (sheet: {sheet_name})')
                    return True
                except PermissionError:
                    attempt += 1
                    print(f'⚠️ Permission denied when saving Excel. Ensure the file is closed. Retry {attempt}/{max_retries} ...')
                    time.sleep(4)
                except FileNotFoundError:
                    try:
                        with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
                            df_to_save.to_excel(writer, sheet_name, index=False)
                        print(f'✅ Excel created and saved: {file_path} (sheet: {sheet_name})')
                        return True
                    except Exception as e:
                        print(f'❌ Failed to create Excel: {e}')
                        break
                except Exception as e:
                    print(f'❌ Unexpected error while saving Excel: {e}')
                    break
            backup_path = file_path.replace('.xlsx', f'_backup_{int(time.time())}.xlsx')
            try:
                with pd.ExcelWriter(backup_path, engine='openpyxl', mode='w') as writer:
                    df_to_save.to_excel(writer, sheet_name, index=False)
                print(f'❌ Could not save original file. Saved backup: {backup_path}')
                return False
            except Exception as e:
                print(f'❌ Failed to save backup file as well: {e}')
                return False

        def phase1_send_deletes(df_in, headers, delete_api=None, per_call_sleep=0.4):
            if delete_api is None:
                delete_api = DELETE_PLOT_API
            print('===========================================')
            print('🔁 PHASE 1: Sending DELETE request for all rows')
            print('===========================================')
            for idx, row in df_in.iterrows():
                plot_id = row.get('id', '')
                if pd.isna(plot_id) or str(plot_id).strip() == '':
                    print(f'⚠️ Row {idx + 1}: Empty ID → skipping')
                    df_in.at[idx, 'deletion response'] = 'Skipped: empty id'
                    df_in.at[idx, 'deletion status'] = 'Skipped'
                    df_in.at[idx, 'request id'] = ''
                    continue
                print(f'🧭 Row {idx + 1}: Sending delete for Plot ID {plot_id}')
                try:
                    resp = _log_post(delete_api, json=[plot_id], headers=headers, timeout=60)
                except Exception as e:
                    df_in.at[idx, 'deletion response'] = f'Exception: {e}'
                    df_in.at[idx, 'deletion status'] = 'Delete Failed'
                    df_in.at[idx, 'request id'] = ''
                    print(f'    ❌ Exception during delete call: {e}')
                    time.sleep(per_call_sleep)
                    continue
                if resp.status_code == 200:
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = resp.text
                    df_in.at[idx, 'deletion response'] = str(resp_json)
                    req_id = ''
                    if isinstance(resp_json, dict):
                        req_id = resp_json.get('id') or resp_json.get('requestId') or resp_json.get('request_id') or ''
                        if not req_id:
                            for v in resp_json.values():
                                if isinstance(v, dict):
                                    req_id = v.get('id') or v.get('requestId') or ''
                                    if req_id:
                                        break
                    elif isinstance(resp_json, list) and len(resp_json) > 0 and isinstance(resp_json[0], dict):
                        req_id = resp_json[0].get('id') or resp_json[0].get('requestId') or ''
                    df_in.at[idx, 'request id'] = req_id or ''
                    del_stat = 'Queued'
                    if isinstance(resp_json, dict):
                        del_stat = resp_json.get('status', 'Queued')
                    df_in.at[idx, 'deletion status'] = del_stat
                    print(f'    ✔️ Delete queued. Request Id: {req_id or 'N/A'}')
                else:
                    df_in.at[idx, 'deletion response'] = f'Error {resp.status_code}: {resp.text}'
                    df_in.at[idx, 'deletion status'] = 'Delete Failed'
                    df_in.at[idx, 'request id'] = ''
                    df_in.at[idx, 'Status'] = 'Failed'
                    df_in.at[idx, 'APIresponse'] = f'Error {resp.status_code}: {resp.text}'
                    print(f'    ❌ Delete failed (HTTP {resp.status_code}) for Plot ID {plot_id}')
                time.sleep(per_call_sleep)
            return df_in

        def phase2_check_status(df_in, headers, status_api_template=None, post_delete_pause=8, per_status_sleep=0.4, max_status_attempts=1):
            if status_api_template is None:
                status_api_template = STATUS_CHECK_API
            print('\n⏳ Waiting fixed period before status checks...')
            time.sleep(post_delete_pause)
            print('===========================================')
            print('🔁 PHASE 2: Checking STATUS for all rows')
            print('===========================================')
            for idx, row in df_in.iterrows():
                plot_id = row.get('id', '')
                req_id = row.get('request id', '')
                if pd.isna(plot_id) or str(plot_id).strip() == '':
                    continue
                if not req_id or str(req_id).strip() == '':
                    current_resp = str(row.get('deletion response', ''))
                    if 'Error' in current_resp or 'Exception' in current_resp:
                        df_in.at[idx, 'deletion status'] = 'Delete failed - no request id'
                        print(f'⚠️ Row {idx + 1}: No request id; delete failed earlier.')
                    else:
                        try:
                            print(f'🔎 Row {idx + 1}: No request id; attempting fallback status check using Plot ID {plot_id}')
                            fallback_resp = _log_get(status_api_template.format(plot_id), headers=headers, timeout=40)
                            if fallback_resp.status_code == 200:
                                try:
                                    fallback_json = fallback_resp.json()
                                except Exception:
                                    fallback_json = fallback_resp.text
                                df_in.at[idx, 'deletion status'] = str(fallback_json)
                                print(f'    🔄 Fallback status returned')
                            else:
                                df_in.at[idx, 'deletion status'] = f'No request id; fallback error {fallback_resp.status_code}'
                                print(f'    ❌ Fallback status failed: {fallback_resp.status_code}')
                        except Exception as e:
                            df_in.at[idx, 'deletion status'] = f'No request id; fallback exception: {e}'
                            print(f'    ❌ Exception during fallback: {e}')
                    time.sleep(per_status_sleep)
                    continue
                status_value = None
                for attempt in range(1, max_status_attempts + 1):
                    try:
                        status_resp = _log_get(status_api_template.format(req_id), headers=headers, timeout=60)
                    except Exception as e:
                        status_value = f'Exception: {e}'
                        print(f'    ❌ Exception while checking status for RequestId {req_id}: {e}')
                        break
                    if status_resp.status_code == 200:
                        try:
                            status_json = status_resp.json()
                        except Exception:
                            status_json = status_resp.text
                        status_value = str(status_json)
                        print(f'    🔄 Row {idx + 1}: Status retrieved')
                        break
                    else:
                        status_value = f'Error {status_resp.status_code}: {status_resp.text}'
                        print(f'    ❌ Status check attempt {attempt} failed for RequestId {req_id} (HTTP {status_resp.status_code})')
                        if attempt < max_status_attempts:
                            time.sleep(per_status_sleep)
                        if attempt < max_status_attempts:
                            time.sleep(per_status_sleep)
                if 'Exception' in (status_value or '') or 'Error' in (status_value or ''):
                    df_in.at[idx, 'Status'] = 'Failed'
                else:
                    df_in.at[idx, 'Status'] = 'Success'
                df_in.at[idx, 'APIresponse'] = status_value or 'No status returned'
                time.sleep(per_status_sleep)
            return df_in

        def main():
            start_time = datetime.now()
            print('🔄 Starting Plot deletion process...')
            updated_df = phase1_send_deletes(df, headers, delete_api=DELETE_PLOT_API, per_call_sleep=0.4)
            updated_df = phase2_check_status(updated_df, headers, status_api_template=STATUS_CHECK_API, post_delete_pause=8, per_status_sleep=0.4, max_status_attempts=1)
            if len(updated_df.columns) > 0:
                pass
            saved = save_df_to_excel(updated_df, file_path, sheet_name)
            if not saved:
                print('⚠️ Could not save to original file; backup created.')
            end_time = datetime.now()
            elapsed = end_time - start_time
            print('======================================================')
            print(f'Start Time : {start_time}')
            print(f'End Time   : {end_time}')
            print(f'Elapsed    : {elapsed}')
            print('======================================================')
        print(f'📂 Loading Excel: {file_path}')
        print('🔄 Requesting access token...')
        if not token:
            print('❌ Failed to retrieve token. Exiting.')
            raise SystemExit(1)
        wb = MockWorkbook(builtins)
        if env_sheet_name not in wb.sheetnames:
            raise RuntimeError(f"❌ Sheet '{env_sheet_name}' not found in workbook")
        env_sheet = wb[env_sheet_name]
        for r in range(2, env_sheet.max_row + 1):
            raw = env_sheet.cell(row=r, column=1).value
            if raw and str(raw).strip().lower() == 'environment':
                break
        if env_key:
            for r in range(2, env_sheet.max_row + 1):
                raw = env_sheet.cell(row=r, column=1).value
                if raw and str(raw).strip().lower() == env_key.lower():
                    env_url = base_url
                    break
        if not env_url:
            env_url = builtins.env_config.get('apiBaseUrl', '')
        print(f'🌍 Using Base URL: {env_url}')
        df.columns = [c.strip().lower() for c in df.columns]
        print('Columns in Excel:', df.columns.tolist())
        print('First few rows:\n', df.head())
        for col in ['deletion response', 'deletion status', 'request id']:
            if col not in df.columns:
                df[col] = ''
            else:
                df[col] = df[col].astype(str)
        if 'id' not in df.columns:
            raise RuntimeError("❌ Required column 'id' not found in Plot_details sheet")
        if True:
            parser = argparse.ArgumentParser(description='Plot deletion processor (standalone)')
            parser.add_argument('--file', '-f', default=file_path, help='Path to Excel file')
            parser.add_argument('--sheet', '-s', default=sheet_name, help='Sheet name containing plots')
            args = parser.parse_args()
            file_override = args.file
            sheet_override = args.sheet
            if file_override and file_override != file_path:
                print(f'📂 Using file override: {file_path}')
                wb = MockWorkbook(builtins)
                if env_sheet_name not in wb.sheetnames:
                    raise RuntimeError(f"❌ Sheet '{env_sheet_name}' not found in workbook")
                env_sheet = wb[env_sheet_name]
                for r in range(2, env_sheet.max_row + 1):
                    raw = env_sheet.cell(row=r, column=1).value
                    if raw and str(raw).strip().lower() == 'environment':
                        break
                env_url = base_url
                if env_key:
                    for r in range(2, env_sheet.max_row + 1):
                        raw = env_sheet.cell(row=r, column=1).value
                        if raw and str(raw).strip().lower() == env_key.lower():
                            env_url = base_url
                            break
                if not env_url:
                    env_url = builtins.env_config.get('apiBaseUrl', '')
                env_url = base_url
                DELETE_PLOT_API = f'{env_url}/services/farm/api/intelligence/croppable-areas/request'
                STATUS_CHECK_API = f'{env_url}/services/farm/api/intelligence/croppable-areas/request/status?requestId={{}}'
                df = builtins.data_df
                df.columns = [c.strip().lower() for c in df.columns]
                for col in ['deletion response', 'deletion status', 'request id']:
                    if col not in df.columns:
                        df[col] = ''
                    else:
                        df[col] = df[col].astype(str)
            main()
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