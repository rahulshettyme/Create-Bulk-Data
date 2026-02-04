import concurrent.futures
import builtins
import pandas as pd
import requests, json, time
from datetime import datetime

def run(data, token, env_config):
    builtins.data = data
    builtins.token = token
    builtins.base_url = env_config.get('apiBaseUrl')
    base_url = builtins.base_url
    base_url = builtins.base_url
    env_key = env_config.get('environment')
    file_path = 'Uploaded_File.xlsx'
    builtins.file_path = file_path
    env_url = base_url
    builtins.env_url = base_url

    class MockCell:

        def __init__(self):
            self.value = None

    class MockSheet:

        def __init__(self, data):
            self.data = data

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

        def __init__(self, data):
            self.data = data

        def __getitem__(self, key):
            return MockSheet(self.data)

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
    wk = MockWorkbook(data)
    builtins.wk = wk

    def _log_req(method, url, **kwargs):
        import requests
        import json
        payload = kwargs.get('json') or kwargs.get('data') or 'No Payload'
        print(f'[TRACE_API_REQ] Method: {method} | URL: {url} | Params/Body: {payload}')
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
            print(f'[TRACE_API_RESP] Status: {resp.status_code} | Body: {body_preview}')
            return resp
        except Exception as e:
            print(f'[TRACE_API_ERR] {e}')
            raise e

    def _log_get(url, **kwargs):
        return _log_req('GET', url, **kwargs)

    def _log_post(url, **kwargs):
        return _log_req('POST', url, **kwargs)

    def _log_put(url, **kwargs):
        return _log_req('PUT', url, **kwargs)
    start_time = datetime.now()
    print(f'📂 Loading Excel: {file_path}')
    sh = wk['Plot_details']
    rows = sh.max_row
    print('🔄 Requesting access token...')
    if not token:
        print('❌ Failed to retrieve token. Exiting.')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    env_sheet = wk['Environment_Details']
    env_url = base_url
    for r in range(2, env_sheet.max_row + 1):
        param = str(env_sheet.cell(row=r, column=1).value).strip()
        if param.lower() == 'environment':
            break
    for r in range(2, env_sheet.max_row + 1):
        param = str(env_sheet.cell(row=r, column=1).value).strip()
        if param.lower() == env_key.lower():
            env_url = base_url
            break
    print(f'🌍 Using Base URL: {env_url}')
    API_URL = f'{env_url}/services/farm/api/croppable-areas/plot-risk/batch'
    for r in range(2, rows + 1):
        croppable_area_id = sh.cell(row=r, column=1).value
        ca_name = sh.cell(row=r, column=2).value
        farmer_id = sh.cell(row=r, column=3).value
        if croppable_area_id is None or str(croppable_area_id).strip() == '':
            print(f'🛑 Empty row encountered at Row {r}. Stopping execution.')
            break
        payload = [{'croppableAreaId': int(croppable_area_id), 'farmerId': None if farmer_id in [None, ''] else farmer_id}]
        try:
            response = _log_post(API_URL, headers=headers, json=payload)
            resp_json = response.json()
        except Exception as e:
            print(f'❌ Error at row {r}: {e}')
            sh.cell(row=r, column=4).value = 'Failed'
            sh.cell(row=r, column=5).value = str(e)
            sh.cell(row=r, column=6).value = ''
            sh.cell(row=r, column=7).value = ''
            continue
        sh.cell(row=r, column=7).value = json.dumps(resp_json, ensure_ascii=False)
        sr_details = {}
        if isinstance(resp_json.get('srPlotDetails'), dict):
            sr_details = list(resp_json['srPlotDetails'].values())[0]
        error_val = sr_details.get('error')
        message_val = sr_details.get('message', '')
        srplot_id_val = sr_details.get('srPlotId', '')
        if error_val:
            status_val = 'Failed'
        else:
            status_val = 'Success'
        sh.cell(row=r, column=4).value = status_val
        sh.cell(row=r, column=5).value = message_val
        sh.cell(row=r, column=6).value = srplot_id_val
        print(f'➡️ Row {r} | CA_ID: {croppable_area_id} | Status: {status_val} | Message: {message_val} | SRPlotID: {srplot_id_val}')
    wk.save(file_path)
    print(f"\n✅ Excel file '{file_path}' updated successfully.")
    print('🏁 Execution completed.')
    end_time = datetime.now()
    elapsed_time = end_time - start_time
    print(f'Start Time : {start_time}')
    print(f'End Time   : {end_time}')
    print(f'Elapsed    : {elapsed_time}')
    pass
    return data
