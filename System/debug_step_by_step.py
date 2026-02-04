import requests
import json
import pandas as pd

# --- USER INPUTS ---
ENV = "QA2"
TENANT = "qa2wt"
USER = "1234560001"
PASS = "test"
PLOT_ID = "15103"  # UPDATED ID

# --- 1. LOGIN STEP ---
print("\n[STEP 1] LOGIN")
print(f"Goal: Get Bearer Token for {USER} in {TENANT}")
SSO_URL = "https://v2sso-gcp.cropin.co.in/auth/realms/qa2wt/protocol/openid-connect/token"
payload = {
    "username": USER,
    "password": PASS,
    "grant_type": "password",
    "client_id": "resource_server",
    "client_secret": "resource_server",
    "scope": "openid"
}
try:
    resp = requests.post(SSO_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if resp.status_code == 200:
        token = resp.json().get('access_token')
        print(f"[OK] Login Successful. Token: {token[:15]}... (truncated)")
    else:
        print(f"[FAIL] Login Failed: {resp.text}")
        exit(1)
except Exception as e:
    print(f"[FAIL] Login Exception: {e}")
    exit(1)

# --- 2. SCRIPT VARIABLES & API CONSTRUCTION ---
print("\n[STEP 2] CONSTRUCT API URL")
base_url = "https://sf-v2-gcp.cropin.co.in/qa2"
# Logic from script: DELETE_API = f"{base_url}/delete" (Wait, original script used hardcoded path?)
# Let's use the logic I verified in TEST script: 
# DELETE_PLOT_API = f'{env_url}/services/farm/api/intelligence/croppable-areas/request'
DELETE_API = f"{base_url}/services/farm/api/intelligence/croppable-areas/request"

print(f"Base URL: {base_url}")
print(f"Constructed DELETE_API: {DELETE_API}")

# --- 3. PAYLOAD CONSTRUCTION ---
print("\n[STEP 3] CONSTRUCT PAYLOAD")
# Logic: json=[plot_id]
payload_body = [15104] # TESTING INTEGER: Was [PLOT_ID] (String)
print(f"Row ID from Excel: 15104 (Integer)")
print(f"Final JSON Payload: {json.dumps(payload_body)}")

# --- 4. EXECUTION ---
print("\n[STEP 4] EXECUTE API REQUEST")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
print(f"Request Method: POST")
print(f"Request URL: {DELETE_API}")
# print(f"Request Headers: {headers}") 

try:
    api_resp = requests.post(DELETE_API, json=payload_body, headers=headers)
    print(f"Response Status Code: {api_resp.status_code}")
    print(f"Response Body Raw: {api_resp.text}")
    
    try:
        resp_json = api_resp.json()
        print(f"Response Parsed JSON: {json.dumps(resp_json, indent=2)}")
    except:
        resp_json = api_resp.text
        print("Response is not JSON.")

except Exception as e:
    print(f"[FAIL] Request Failed: {e}")
    exit(1)

# --- 5. DATA EXTRACTION & SAVING ---
print("\n[STEP 5] EXTRACT DATA FOR EXCEL")

# Logic from script:
# df_in.at[idx, 'deletion response'] = str(resp_json)
# req_id = resp_json.get('id') or resp_json.get('requestId') ...
# df_in.at[idx, 'request id'] = req_id
# df_in.at[idx, 'deletion status'] = 'Delete Failed' (if not 200)

excel_updates = {}

if api_resp.status_code == 200:
    # 'deletion response' column
    excel_updates['deletion response'] = str(resp_json)
    
    # 'request id' column
    req_id = ''
    if isinstance(resp_json, dict):
        req_id = resp_json.get('id') or resp_json.get('requestId') or ''
    elif isinstance(resp_json, list) and len(resp_json) > 0:
        req_id = resp_json[0].get('id')
        
    excel_updates['request id'] = req_id
    print(f"[OK] Success! Data extracted:")
    print(f"   -> Column 'deletion response': {excel_updates['deletion response']}")
    print(f"   -> Column 'request id': {excel_updates['request id']}")

    # --- PHASE 2: STATUS CHECK (Simulated) ---
    print("\n[STEP 6] PHASE 2: CHECK STATUS")
    if req_id:
        # Construct Status API
        # Original: f"{env_url}/services/farm/api/intelligence/croppable-areas/request/status?requestId={{}}"
        STATUS_API_TEMPLATE = f"{base_url}/services/farm/api/intelligence/croppable-areas/request/status?requestId={{}}"
        STATUS_URL = STATUS_API_TEMPLATE.format(req_id)
        
        print(f"Constructed STATUS_URL: {STATUS_URL}")
        
        try:
            print(f"Sending GET request...")
            # Headers same as before
            status_resp = requests.get(STATUS_URL, headers=headers)
            print(f"Response Status: {status_resp.status_code}")
            print(f"Response Body: {status_resp.text}")
        except Exception as e:
            print(f"[FAIL] Status Check Failed: {e}")
    else:
        print("[SKIP] No Request ID to check status.")

else:
    # Failure Logic
    excel_updates['deletion response'] = f"Error {api_resp.status_code}: {api_resp.text}"
    excel_updates['deletion status'] = "Delete Failed"
    print(f"[FAIL] Failed! Data extracted:")
    print(f"   -> Column 'deletion response': {excel_updates['deletion response']}")
    print(f"   -> Column 'deletion status': {excel_updates['deletion status']}")
