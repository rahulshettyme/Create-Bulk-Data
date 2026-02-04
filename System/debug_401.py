import requests
import json

# CONFIG
ENV = "QA2"
TENANT = "qa2wt"
USER = "1234560001"
PASS = "test"
PLOT_ID = "15102"

# 1. CONSTRUCT URLs
SSO_PREFIX = "https://v2sso-gcp.cropin.co.in/auth/realms/"
SSO_SUFFIX = "/protocol/openid-connect/token"
SSO_URL = f"{SSO_PREFIX}{TENANT}{SSO_SUFFIX}"

API_BASE = "https://sf-v2-gcp.cropin.co.in/qa2"
DELETE_API = f"{API_BASE}/services/farm/api/intelligence/croppable-areas/request"

print(f"--- 1. CONFIGURATION ---")
print(f"SSO URL: {SSO_URL}")
print(f"API URL: {DELETE_API}")

# 2. GET TOKEN
print(f"\n--- 2. AUTHENTICATION ---")
payload = {
    "username": USER,
    "password": PASS,
    "grant_type": "password",
    "client_id": "cropin-app" # Guessing typical keycloak client
}
# Need to check if client_id is needed. Often 'cropin-web' or 'cropin-app'. 
# I will try without first, or check if I can find it in source code. 
# Let's try standard 'cropin-app' or just user/pass/grant_type if allowed.
# Actually, looking at `db.json`, it doesn't list client_id. 
# I will try a generic request first.

try:
    print(f"Logging in user: {USER}...")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    # Note: Keycloak typically needs client_id. 
    # Let me try 'cropin-mobile' or 'web' if I don't know. 
    # Or maybe I can assume the token passed by the user previously was valid and just check validty?
    # No, I need to generate one to prove credentials work.
    
    # Let's peek at `server.js` or `script_management.js` component `LoginComponent`? 
    # `script_management.js` uses `LoginComponent`. 
    # I can try to read `components/LoginComponent.js` if it exists.
    
    # Updated Client ID from backend/api.js
    payload["client_id"] = "resource_server"
    payload["client_secret"] = "resource_server"
    payload["scope"] = "openid"
    
    resp = requests.post(SSO_URL, data=payload, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Login Failed: {resp.text}")
        exit(1)
             
    token_data = resp.json()
    token = token_data.get('access_token')
    
    # SAVE TOKEN TO FILE
    with open("valid_token.txt", "w") as f:
        f.write(token)
        
    print(f"Status: 200")
    print("Token received successfully and saved to valid_token.txt.")
    
except Exception as e:
    print(f"Auth Exception: {e}")
    exit(1)

# 3. DELETE CALL
print(f"\n--- 3. DELETE REQUEST ---")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
body = [PLOT_ID]

print(f"Sending DELETE to {DELETE_API}")
print(f"Payload: {body}")
print(f"Headers: Authorization: Bearer {token[:10]}...")

try:
    # Requests DELETE usually doesn't take 'json' arg in older versions? 
    # Python requests supports it.
    del_resp = requests.post(DELETE_API, json=body, headers=headers)
    
    print(f"Response Status: {del_resp.status_code}")
    print(f"Response Body: {del_resp.text}")
    print(f"Response Headers: {del_resp.headers}")

except Exception as e:
    print(f"Delete Exception: {e}")
