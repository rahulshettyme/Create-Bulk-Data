
import sys
import json
import os
import requests
import re

def sanitize_code(code: str) -> str:
    """Sanitizes sensitive information like JWT tokens from the code."""
    jwt_pattern = r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+'
    sanitized = re.sub(jwt_pattern, '"<REDACTED_ACCESS_TOKEN>"', code)
    return sanitized

def get_gemini_api_key():
    """Fetches Gemini API Key from Env Var, System/secrets.json or System/db.json"""
    # Priority 1: Environment Variable
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if key: return key
    
    # Priority 2: System/secrets.json or System/db.json
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
        for filename in ["secrets.json", "db.json"]:
            path = os.path.join(base_dir, "System", filename)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    k = data.get("google_api_key", "").strip() or data.get("gemini_api_key", "").strip()
                    if k: return k
    except: pass
    return ""

def generate_heuristic_script(description):
    """Fallback: Generates a Python script by parsing the structured description directly."""
    import textwrap
    import re
    
    desc_lines = description.splitlines()
    imports = ["import requests", "import json", "import thread_utils"]
    
    generated_steps = []
    
    def flush_api_step(v_name, meth, u, pay, instr):
        v_name = v_name.replace(' ', '_')
        url_var = f"{v_name}_url"
        code = f"""
            # API Step: {v_name}
            {url_var} = f"{{base_url}}{u}"
            payload = {{}} # Construct from: {pay}
            {v_name} = requests.{meth.lower()}({url_var}, json=payload, headers={{'Authorization': token}})
            row['{v_name}_status'] = {v_name}.status_code
        """
        return textwrap.dedent(code).strip()

    steps = re.split(r'Step \d+ \[', description)
    for step_block in steps:
        if not step_block.strip(): continue
        step_type = "API" if step_block.startswith("API") else "LOGIC"
        content = step_block
        if step_type == "API":
            v_name = (re.search(r'- Step/Variable Name: (.*)', content).group(1).strip() if re.search(r'- Step/Variable Name: (.*)', content) else "api_resp")
            meth = (re.search(r'- Call (\w+) (.*)', content).group(1).strip() if re.search(r'- Call (\w+) (.*)', content) else "POST")
            u = (re.search(r'- Call (\w+) (.*)', content).group(2).strip() if re.search(r'- Call (\w+) (.*)', content) else "/url")
            pay = (re.search(r'- Payload Example: (.*)', content).group(1).strip() if re.search(r'- Payload Example: (.*)', content) else "{}")
            instr = (re.search(r'- Instructions: (.*)', content).group(1).strip() if re.search(r'- Instructions: (.*)', content) else "")
            generated_steps.append(flush_api_step(v_name, meth, u, pay, instr))
        elif step_type == "LOGIC":
            logic_text = re.search(r'- Logic: (.*)', content, re.DOTALL).group(1).strip() if re.search(r'- Logic: (.*)', content, re.DOTALL) else "Logic..."
            generated_steps.append(f"# LOGIC: {logic_text.replace(chr(10), ' ')}")

    if not generated_steps:
        generated_steps.append("# No steps detected. Manual implementation required.")

    steps_code_indented = textwrap.indent("\n\n".join(generated_steps), '            ')

    return f"""import requests
import json
import thread_utils

def run(data, token, env_config):
    base_url = env_config.get('apiBaseUrl')
    def process_row(row):
        try:
{steps_code_indented}
        except Exception as e:
            row['Error'] = str(e)
        return row
    return thread_utils.run_in_parallel(process_func=process_row, items=data)
"""

def _get_ist_header(base_text):
    from datetime import datetime, timedelta
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return f"# {base_text} - {ist_time.strftime('%Y-%m-%d %H:%M:%S IST')}"

def clean_ai_headers(script_content):
    lines = script_content.splitlines()
    cleaned_lines = []
    stripping = True
    for line in lines:
        s = line.strip()
        if stripping:
            if not s: continue
            sl = s.lower()
            if sl.startswith(("# ai generated", "# ai updated", "# ai generation failed", "# ai update failed", "# original code:", "EXPECTED_INPUT_COLUMNS")): continue
            if s.startswith(('import ', 'from ', 'def ', 'class ', '@', 'if ', 'try:', 'print(')): stripping = False
            else: continue
        
        # AGGRESSIVE CLEANUP: Remove detected legacy logging wrappers
        if "def _log_req" in s or "def _log_get" in s or "def _log_post" in s or "def _log_put" in s:
            continue
        if "[API_DEBUG]" in s and "print(" in s:
            continue
            
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def _get_applicable_models(api_key):
    """
    Fetches available models from Google API and returns a prioritized list of Gemini models.
    """
    models = []
    try:
        resp = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            for m in data.get('models', []):
                name = m['name'].replace('models/', '')
                if 'gemini' in name.lower() and 'generateContent' in m.get('supportedGenerationMethods', []):
                    models.append(name)
    except: pass
    
    # Priority sorting
    def priority(name):
        n = name.lower()
        if '2.0-flash' in n: return 0
        if '1.5-pro' in n: return 1
        if '1.5-flash' in n: return 2
        if 'pro' in n: return 3
        if 'flash' in n: return 4
        return 10

    models.sort(key=priority)
    
    # Default fallbacks if discovery failed
    if not models:
        models = ["gemini-1.5-flash", "gemini-pro"]
        
    return list(dict.fromkeys(models))

def _call_gemini_with_candidates(api_key, models_to_try, payload):
    import time
    last_err = "No models tried"
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, timeout=90)
                if resp.status_code == 200:
                    text = resp.json()['candidates'][0]['content']['parts'][0]['text']
                    if "```python" in text: text = text.split("```python")[1].split("```")[0].strip()
                    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
                    return True, text.strip(), None
                
                err_msg = resp.text[:150]
                last_err = f"{model}: {resp.status_code} {err_msg}"
                
                if resp.status_code in [404, 403, 400]:
                    break # Try next model
                    
                if resp.status_code in [429, 503]:
                    time.sleep(2)
                else:
                    break
            except Exception as e:
                last_err = str(e)
                time.sleep(1)
    return False, None, last_err

def generate_script(description, is_multithreaded=True, input_columns=None, allow_additional_attributes=False, enable_geofencing=False, output_config=None):
    api_key = get_gemini_api_key()
    if not api_key: return generate_heuristic_script(description)

    import_ins = ["requests", "json"]
    if is_multithreaded: 
        import_ins.append("thread_utils")
        import_ins.append("builtins")  # Required for accessing token/env_config in multithreaded scripts
    if enable_geofencing: import_ins.append("components.geofence_utils as geofence_utils")
    if allow_additional_attributes: import_ins.append("components.attribute_utils as attribute_utils")
    
    # Check if description contains Master Search steps
    has_master_search = "[Master Search]" in description or "[MASTER SEARCH]" in description.upper()
    if has_master_search: import_ins.append("master_search")
    
    col_req = f"\n    CRITICAL - INPUT COLUMNS: {input_columns}" if input_columns else ""
    run_req = "In run() function: return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config). CRITICAL: process_row must have signature 'def process_row(row)' - token and env_config are injected into builtins by thread_utils, access them as builtins.token and builtins.env_config inside process_row." if is_multithreaded else "execute sequentially by iterating data"

    prompt = f"You are a Python expert. Description: {description}. {col_req}. Requirements: def run(data, token, env_config), import {', '.join(import_ins)}. {run_req}."
    if allow_additional_attributes: prompt += "\nNOTE: 'Allow Additional Attributes' is ENABLED. The script executor will AUTOMATICALLY inject additional attributes into your API payloads (json or DTO). You do NOT need to manually call attribute_utils, but you MUST ensure your core payload structure is correct."
    if enable_geofencing: prompt += "\nCRITICAL REQUIREMENT: Dynamic Geofencing is ENABLED. You MUST import components.geofence_utils as geofence_utils and use 'geofence_utils.check_geofence(lat, lon, env_config.get('targetLocation'), env_config.get('Geocoding_api_key'), cache=geo_cache)' to validate coordinates. Do NOT use hardcoded polygons. Do NOT fallback to simplified logic. Trust that geofence_utils is available."
    
    # Add explicit import syntax requirements to prevent AI confusion
    prompt += "\n\nCRITICAL IMPORT SYNTAX - Use EXACTLY these import statements:"
    prompt += "\nimport requests"
    prompt += "\nimport json"
    if is_multithreaded:
        prompt += "\nimport thread_utils  # Direct import, NOT 'from components import thread_utils'"
        prompt += "\nimport builtins  # Required for accessing token/env_config"
    if enable_geofencing:
        prompt += "\nimport components.geofence_utils_v2 as geofence_utils  # CRITICAL: Use V2, NOT V1"
        prompt += "\n# FORBIDDEN: Do NOT use 'import components.geofence_utils' - MUST use geofence_utils_v2"
    if has_master_search:
        prompt += "\nimport components.master_search as master_search  # NOT 'from components import master_search'"
    
    if is_multithreaded:
        prompt += "\n\nCRITICAL THREAD SAFETY: If you use module-level caches (e.g., _geocode_cache = {}), YOU MUST USE A LOCK for thread-safe access to PREVENT data corruption and runtime errors. Use 'thread_utils.create_lock()' at the module level to create a lock. Example: `_lock = thread_utils.create_lock()`. Then pulse 'with _lock:' whenever you read/write to the cache dict inside process_row."
    
    if output_config and output_config.get('isDynamicUI'):
        ui_mapping = output_config.get('uiMapping', [])
        prompt += "\n\nCRITICAL OUTPUT REQUIREMENT: The script logic MUST populate the output 'row' dictionary with the following keys exactly as specified:"
        for m in ui_mapping:
             prompt += f"\n- Key '{m['colName']}': {m['logic']} (Source Value: {m['value']})"
        prompt += "\nEnsure these keys exist in the 'row' dictionary returned by process_row. Do not output 'Name', 'Code', 'Response' unless explicitly asked."
        prompt += "\nCRITICAL: Do NOT create duplicate output keys with minor variations (e.g. 'Farmer ID' and 'FarmerID'). If 'Farmer ID' is required by the UI and mentioned in input columns, use ONLY that key. Do not add 'FarmerID' as a separate key."

    prompt += """\n\nCRITICAL LOGGING REQUIREMENTS:
1. SUPPORT APIs (User lookup, Geofence, Master data) - MUST ALWAYS LOG:
   - ALWAYS add minimal logging for these APIs
   - Format: print(f"[LOOKUP_TYPE] {input} → Result: {output_summary}")
   - Example: print(f"[USER_LOOKUP] {user_name} → ID: {user_id or 'Not Found'}")
   - Example: print(f"[GEOFENCE] {location} → lat={lat:.6f}, lng={lng:.6f}")
   - DO NOT print full API request/response bodies, just the summary
   - These logs are CRITICAL for debugging - do not skip them

2. MAIN/FINAL API call (the primary purpose of the script, e.g., Create Farmer):
   - DO NOT add manual [API_DEBUG] print statements
   - The automatic wrapper will handle detailed logging for the main API

3. GENERAL:
   - Keep log output concise but informative
   - Always log the outcome of lookups (found/not found)
   - Always log coordinates from geofence calls

2. CRITICAL PAYLOAD HANDLING (Multipart/DTO vs JSON):
   - CHECK if the API Step URL or Description implies a Multipart/DTO upload (vs standard JSON).
   - Signals: "Payload Type: DTO_FILE", "Multipart", "upload", "file".
   - IF MULTIPART/DTO:
     - ❌ DO NOT use `json=payload` or `data=json.dumps(payload)`.
     - ❌ DO NOT set `Content-Type: application/json` header manually.
     - ✅ USE `files` parameter.
     - Code Pattern:
       ```python
       payload_data = { ... } # Construct your dictionary as usual
       # Wrap in Multipart 'dto' part
       files = {
           'dto': (None, json.dumps(payload_data), 'application/json')
       }
       # Execute
       response = requests.post(url, headers={'Authorization': f'Bearer {builtins.token}'}, files=files)
       ```
   - IF STANDARD JSON:
     - Use `requests.post(url, json=payload, ...)`

3. CRITICAL SUCCESS CONDITION:
   - APIs may return 200 (OK) or 201 (Created) for success.
   - ALWAYS check `if response.ok:` or `if response.status_code in [200, 201]:`.
   - ❌ DO NOT check `if response.status_code == 200:` (This causes false failures for 201).

4. CRITICAL DATA VALIDATION - PHONE NUMBERS:
   - If the input description mentions 'Phone Number' or 'Mobile Number', YOU MUST ENFORCE STRICT FORMATTING.
   - The allowed format is exact: "91 9876543210" or "91-9876543210" (Country Code [space/hyphen] Mobile Number).
   - Validation Logic (Python):
     ```python
     phone_raw = str(row.get('Phone Number', '')).strip()
     if ' ' in phone_raw:
         parts = phone_raw.split(' ')
     elif '-' in phone_raw:
         parts = phone_raw.split('-')
     else:
         row['Status'] = 'Fail'
         # CRITICAL: Use this EXACT error message format
         row['Response'] = 'Invalid phone number format. Required in 91 9876543210' 
         return row

     if len(parts) != 2:
         row['Status'] = 'Fail'
         row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
         return row

     country_code = "+" + parts[0]
     mobile_number = parts[1]
     ```
   - Use `country_code` and `mobile_number` in your API payload.
   - Do NOT default to +91 if the format is wrong. FAIL THE ROW."""
    
    prompt += """

2. CRITICAL PAYLOAD HANDLING (Multipart/DTO vs JSON):
   - CHECK if the API Step URL or Description implies a Multipart/DTO upload (vs standard JSON).
   - Signals: "Payload Type: DTO_FILE", "Multipart", "upload", "file".
   - IF MULTIPART/DTO:
     - ❌ STRICTLY FORBIDDEN: DO NOT use `json=payload` or `data=json.dumps(payload)`.
     - ❌ STRICTLY FORBIDDEN: DO NOT set `Content-Type: application/json` header manually.
     - ✅ MUST USE `files` parameter.
     - Code Pattern:
       ```python
       payload_data = { ... } # Construct dictionary
       # Wrap in Multipart 'dto' - CRITICAL STRUCTURE
       files = {
           'dto': (None, json.dumps(payload_data), 'application/json')
       }
       # Execute
       response = requests.post(url, headers={'Authorization': f'Bearer {builtins.token}'}, files=files)
       ```
   - IF STANDARD JSON:
     - Use `requests.post(url, json=payload, ...)`

3. CRITICAL SUCCESS CONDITION:
   - APIs may return 200 (OK) or 201 (Created) for success.
   - ALWAYS check `if response.ok:` or `if response.status_code in [200, 201]:`.
   - ❌ DO NOT check `if response.status_code == 200:` (This causes false failures for 201)."""
    
    prompt += """

CRITICAL URL HANDLING: When constructing API URLs using env_config base_url, do NOT use `urljoin` with a path starting with `/`. It will destroy the path component (e.g. /qa7) of the base URL. Use f-strings like `f'{base_url}/my/api'` or ensure relative paths."""
    
    # Add thread_utils requirements if multithreaded
    if is_multithreaded:
        prompt += """\n\nCRITICAL THREAD_UTILS REQUIREMENTS:
1. FUNCTION SIGNATURE: process_row MUST have signature 'def process_row(row)' - it takes ONLY the row parameter.
2. ACCESSING TOKEN/ENV_CONFIG: thread_utils.run_in_parallel injects token and env_config into builtins.
   - Access them as: builtins.token and builtins.env_config
   - Example: base_url = builtins.env_config.get('apiBaseUrl')
   - Example: headers = {'Authorization': f'Bearer {builtins.token}'}
3. RUN FUNCTION: In run(data, token, env_config), call:
   return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)
4. DO NOT pass token/env_config as parameters to process_row - they are injected via builtins.
5. IMPORT: Add 'import builtins' at the top of the script to access builtins.token and builtins.env_config."""
    
    # ALWAYS add Master Search instructions - these are CRITICAL for any data lookup
    prompt += """\n\nCRITICAL MASTER SEARCH REQUIREMENTS:
🚨 FORBIDDEN: DO NOT write custom API calls for user, farmer, soiltype, irrigationtype, or any master data lookups.
You MUST use the master_search component for ALL master data lookups.

1. IMPORT: Add 'import components.master_search as master_search' at the top

2. MASTER TYPES THAT REQUIRE master_search:
   - 'user' - User lookups (e.g., AssignedTo, Manager, CreatedBy)
   - 'farmer' - Farmer lookups
   - 'soiltype' - Soil type lookups
   - 'irrigationtype' - Irrigation type lookups
   - ANY other master data mentioned in db.json master_data_config

3. INITIALIZE CACHES (🚨 MODULE LEVEL ONLY - OUTSIDE ALL FUNCTIONS):
   - You MUST define these at the very top of your script, after imports.
   - For "search" mode masters (user, farmer): Create empty cache dict
     Example: _user_cache = {}
   - For "once" mode masters (soiltype, irrigationtype): Fetch all data
     CRITICAL: Use a consistent naming pattern: `_{master_type}_list`
     Example: _soiltype_list = master_search.fetch_all('soiltype', builtins.env_config)
   - 🚨 FORBIDDEN: DO NOT initialize these inside the `run()` or `process_row()` functions. They must be GLOBAL.

4. LOOKUP PATTERN (inside process_row function):
   6. MANDATORY LOGIC REPLACEMENT (SEARCH mode - ALL MASTER TYPES):
   🚨 CRITICAL: This optimization applies to ALL search-mode master types (user, farmer, project, etc.)
   
   For EACH search-mode master type in your script, you MUST apply this bypass pattern:
   
   **STEP 1: Detect ID Column at Module Level**
   At the start of run() function, check if the first row has the ID column.
   The column name pattern is typically: '{MasterTypeName}_id' or '{OutputFieldName}'
   
   Examples:
   - For 'user' master → Check for 'UserID' or 'AssignedTo_id' column
   - For 'farmer' master → Check for 'Farmer Name_id' or 'FarmerID' column
   - For 'project' master → Check for 'Project_id' or 'ProjectID' column
   
   **STEP 2: Apply Conditional Logic in process_row()**
   
   ```python
   # EXAMPLE 1: User Master Type
   # At start of run() function (MODULE LEVEL):
   _use_provided_user_ids = bool(data and data[0].get('UserID'))
   
   # Inside process_row(row):
   if _use_provided_user_ids:
       # STRICT MODE: Use provided ID, fail if missing.
       user_id = row.get('UserID')
       if not user_id:
           row['Status'] = 'Fail'
           row['Response'] = 'UserID is empty (Strict Mode)'
           print(f"[USER_LOOKUP] {assigned_to_name} → ID: Not Found (Empty in Strict Mode)")
           return row
       print(f"[USER_LOOKUP] {assigned_to_name} → ID: {user_id} (Provided)")
   else:
       # FALLBACK MODE: Perform Search
       result = master_search.search('user', assigned_to_name, builtins.env_config, _user_cache)
       if not result['found']:
           row['Status'] = 'Fail'
           row['Response'] = result['message']
           return row
       user_id = result['value']
   
   # EXAMPLE 2: Farmer Master Type
   # At start of run() function (MODULE LEVEL):
   _use_provided_farmer_ids = bool(data and data[0].get('Farmer Name_id'))
   
   # Inside process_row(row):
   if _use_provided_farmer_ids:
       # STRICT MODE: Use provided ID, fail if missing.
       farmer_id = row.get('Farmer Name_id')
       if not farmer_id:
           row['Status'] = 'Fail'
           row['Response'] = 'Farmer Name_id is empty (Strict Mode)'
           print(f"[FARMER_LOOKUP] {farmer_name} → ID: Not Found (Empty in Strict Mode)")
           return row
       print(f"[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id} (Provided)")
   else:
       # FALLBACK MODE: Perform Search
       result = master_search.search('farmer', farmer_name, builtins.env_config, _farmer_cache)
       if not result['found']:
           row['Status'] = 'Fail'
           row['Response'] = result['message']
           return row
       farmer_id = result['value']
   ```
   
   🚨 CRITICAL RULES:
   - Apply this pattern to EVERY search-mode master in your script (user, farmer, project, etc.)
   - The bypass variable name should be: `_use_provided_{master_type}_ids`
   - ALWAYS add the print statement for logging whether ID was provided or searched
   - Initialize the bypass flag at the START of run() function, NOT inside process_row()
   
   For ONCE mode (soiltype, irrigationtype):
   ```python
   # Use the exact variable name defined at module level (e.g. _soiltype_list)
   result = master_search.lookup_from_cache(_soiltype_list, 'name', row.get('SoilType'), 'id')
   if not result['found']:
       row['Status'] = 'Fail'
       row['Response'] = result['message']
       return row
   soil_type_id = result['value']
   ```

5. CRITICAL NOTES:
   - master_search handles ALL complexity: path variables, company_id injection, query parameters, caching
   - DO NOT construct /services/user/api/users or /services/authorization URLs manually
   - DO NOT use requests.get() for user/farmer lookups - use master_search.search()
   - The master_data_config in db.json defines all endpoints and parameters
   - search() returns: {'found': bool, 'value': extracted_value, 'message': str}

6. EXAMPLE - User Lookup:
   ❌ WRONG: `user_id = result['value']` (outside the 'if found' block)
   ✅ RIGHT: Ensure variables are only accessed if `result['found']` is True.
   
7. CRITICAL VARIABLE NAMING:
   - 🚨 🚨 DO NOT hallucinate variable names like `_soil_types_data` or `_irrigation_data`.
   - ALWAYS use the name YOU defined at the module level.
   - For "once" mode, the recommended pattern is `_{master_type}_list`.
"""
    
    # Add GEO Step instructions
    prompt += """\n\nCRITICAL GEO STEP REQUIREMENTS:
When the user specifies a GEO Step (address geocoding/geofencing), follow these EXACT steps:

1. IMPORT: Ensure 'import components.geofence_utils as geofence_utils' is at the top

2. FETCH GEOCODE DATA:
   ```python
   geocode_result = geofence_utils.get_boundary(address, builtins.env_config.get('Geocoding_api_key'))
   ```

3. TRANSFORM TO STANDARD FORMAT:
   ```python
   if geocode_result:
       address_component = geofence_utils.parse_address_component(geocode_result)
   ```

4. EXTRACT ONLY REQUIRED FIELDS:
   - parse_address_component() returns ALL available fields from Google API
   - The user's GEO Step will show an EXAMPLE output format
   - CRITICAL: Build your output dict using ONLY the fields shown in the user's example
   - Example: If user shows {"formattedAddress": "...", "country": "...", "latitude": ...}
     Then extract ONLY those fields from address_component:
     ```python
     output = {
         "formattedAddress": address_component.get("formattedAddress"),
         "country": address_component.get("country"),
         "latitude": address_component.get("latitude")
     }
     ```
   - DO NOT include fields the user didn't specify (e.g., if they don't show "bounds", don't include it)
   - Store this output dict as JSON string in the column name specified by user
   - Example: row['Address Component (non mandatory)'] = json.dumps(output)

5. AVAILABLE FIELDS in parse_address_component():
   - Basic: formattedAddress, placeId
   - Coordinates: latitude, longitude
   - Administrative: country, administrativeAreaLevel1-5
   - Locality: locality, sublocalityLevel1-5
   - Postal: postalCode, route, streetNumber
   - Geometry: bounds, viewport, locationType
   - Other: premise, subpremise, neighborhood, colloquialArea

6. CACHING (CRITICAL for performance):
   - Create a module-level cache: _geocode_cache = {}
   - Check cache before API call:
     ```python
     if address in _geocode_cache:
         address_component = _geocode_cache[address]
     else:
         geocode_result = geofence_utils.get_boundary(address, builtins.env_config.get('Geocoding_api_key'))
         address_component = geofence_utils.parse_address_component(geocode_result)
         _geocode_cache[address] = address_component
     ```

6. ERROR HANDLING:
   - If geocode_result is None, set appropriate error message in row['Response']
   - Always log the result: print(f"[GEOFENCE] {address} → lat={lat}, lng={lng}")

7. COLUMN PRESERVATION:
   - IMPORTANT: The `row` dictionary contains all columns from the input Excel.
   - You MUST return the original `row` dictionary with your modifications ('Status', 'Response', etc.)
   - DO NOT create a new dictionary for the return value, as this will drop "Additional Attributes" columns!

8. FORBIDDEN:
   - ❌ DO NOT try to parse address_components array manually
   - ❌ DO NOT use .get('address_components', {}).get('country') - this will fail!
   - ✅ ALWAYS use geofence_utils.parse_address_component() for transformation
"""
    models = _get_applicable_models(api_key)
    success, content, err = _call_gemini_with_candidates(api_key, models, {"contents": [{"parts": [{"text": prompt}]}]})
    
    # Post-processing: Fix API key name for geofence operations
    # The AI often ignores instructions and uses 'google_api_key' instead of 'Geocoding_api_key'
    # This ensures the correct API key is always used for geofence/geocoding operations
    # CRITICAL: Check if the generated code actually uses geofence_utils, not the enable_geofencing flag
    # (enable_geofencing is for runtime target location input, not for detecting component usage)
    if success and 'geofence_utils' in content:
        # Fix: geofence_utils.get_boundary calls should use Geocoding_api_key
        content = content.replace(
            "builtins.env_config.get('google_api_key')",
            "builtins.env_config.get('Geocoding_api_key')"
        )
        content = content.replace(
            'builtins.env_config.get("google_api_key")',
            'builtins.env_config.get("Geocoding_api_key")'
        )
        # Also fix direct env_config references (non-builtins)
        content = content.replace(
            "env_config.get('google_api_key')",
            "env_config.get('Geocoding_api_key')"
        )
        content = content.replace(
            'env_config.get("google_api_key")',
            'env_config.get("Geocoding_api_key")'
        )
    
    # Post-processing: Fix thread_utils parameter name
    # The AI sometimes uses 'process_row=' instead of 'process_func='
    if success and 'thread_utils.run_in_parallel' in content:
        content = content.replace(
            'thread_utils.run_in_parallel(process_row=',
            'thread_utils.run_in_parallel(process_func='
        )
    
    header = _get_ist_header('AI Generated')
    
    # [CONFIG INJECTION]
    header += f"\n# CONFIG: enableGeofencing = {str(enable_geofencing)}"
    header += f"\n# CONFIG: allowAdditionalAttributes = {str(allow_additional_attributes)}"

    if input_columns:
        col_str = ', '.join(input_columns) if isinstance(input_columns, list) else str(input_columns)
        header += f"\n# EXPECTED_INPUT_COLUMNS: {col_str}"
    
    return f"{header}\n{content}" if success else f"# error: {err}\n{generate_heuristic_script(description)}"

def update_script_with_ai(existing_code, description, is_multithreaded=True, input_columns=None, allow_additional_attributes=False, enable_geofencing=False, output_config=None):
    api_key = get_gemini_api_key()
    if not api_key: return "# API Key missing"
    
    code = sanitize_code(clean_ai_headers(existing_code))
    
    prompt = f"Refactor this code to match the NEW description exactly.\n\nNEW DESCRIPTION:\n{description}\n\nEXISTING CODE:\n```python\n{code}\n```\n\nCRITICAL INSTRUCTIONS:\n1. The Description is the SOURCE OF TRUTH. Steps in the code that are NOT in the description MUST be REMOVED.\n2. Specifically, if an API call or logic block exists in the code but is not mentioned in the description, DELETE IT.\n3. Preserve helper functions, imports, and error handling.\n4. Update variable references as needed."
    prompt += "\n\nCRITICAL BEST PRACTICES:\n- Robust JSON Parsing: API responses might be a list `[...]` or a dict `{'data': [...]}`. Handle both cases. Example: `data = resp.json(); items = data if isinstance(data, list) else data.get('data', [])`\n- Robust String Matching: ALWAYS `.strip()` and `.lower()` when comparing strings (e.g. from Excel vs API) to avoid whitespace mismatches.\n- Error Handling: Do NOT use empty `except: pass`. Print error messages if setup steps fail.\n- URL Construction: Do NOT use `urljoin` if the second argument starts with `/` (e.g. `urljoin(base, '/api')`), as it modifies the base URL path. Reuse `base_url` directly with f-strings or strip leading slashes.\n- Environment Config: Use `env_config.get('apiBaseUrl')` as the primary key for the base URL."
    if allow_additional_attributes: prompt += "\nNOTE: 'Allow Additional Attributes' is ENABLED. The script executor now handles this AUTOMATICALLY via payload interception. You can remove manual attribute_utils calls if they exist, or just leave them. Focus on the core API logic."
    if enable_geofencing: prompt += "\nCRITICAL UPDATE: Dynamic Geofencing is ENABLED. Replace any existing hardcoded polygon logic (e.g. INDIA_POLY) with 'geofence_utils.check_geofence(lat, lon, env_config.get('targetLocation'), env_config.get('Geocoding_api_key'), cache=geo_cache)'. Ensure 'geofence_utils_v2 as geofence_utils' is imported."
    
    # Add explicit import syntax requirements
    has_master_search = "[Master Search]" in description or "[MASTER SEARCH]" in description.upper()
    prompt += "\n\nCRITICAL IMPORT SYNTAX - Use EXACTLY these import statements:"
    prompt += "\nimport requests"
    prompt += "\nimport json"
    if is_multithreaded:
        prompt += "\nimport thread_utils  # Direct import, NOT 'from components import thread_utils'"
        prompt += "\nimport builtins  # Required for accessing token/env_config"
    if enable_geofencing:
        prompt += "\nimport components.geofence_utils_v2 as geofence_utils  # CRITICAL: Use V2, NOT V1"
        prompt += "\n# FORBIDDEN: Do NOT use 'import components.geofence_utils' - MUST use geofence_utils_v2"
    if has_master_search:
        prompt += "\nimport components.master_search as master_search  # NOT 'from components import master_search'"
    
    if output_config and output_config.get('isDynamicUI'):
        ui_mapping = output_config.get('uiMapping', [])
        prompt += "\n\nCRITICAL OUTPUT REQUIREMENT: Ensure the script produces a dictionary (row) with the following keys:"
        for m in ui_mapping:
             prompt += f"\n- '{m['colName']}': {m['logic']} (Source: {m['value']})"
        prompt += "\nCRITICAL: Do NOT create duplicate output keys with minor variations (e.g. 'Farmer ID' and 'FarmerID'). If 'Farmer ID' is required by the UI, use ONLY that key. Do not add 'FarmerID' as a separate key."
             
    prompt += """\n\nCRITICAL LOGGING REQUIREMENTS:
1. SUPPORT APIs (User lookup, Geofence, Master data) - MUST ALWAYS LOG:
   - ALWAYS add minimal logging for these APIs
   - Format: print(f"[LOOKUP_TYPE] {input} → Result: {output_summary}")
   - Example: print(f"[USER_LOOKUP] {user_name} → ID: {user_id or 'Not Found'}")
   - Example: print(f"[GEOFENCE] {location} → lat={lat:.6f}, lng={lng:.6f}")
   - DO NOT print full API request/response bodies, just the summary
   - These logs are CRITICAL for debugging - do not skip them

2. MAIN/FINAL API call (the primary purpose of the script, e.g., Create Farmer):
   - DO NOT add manual [API_DEBUG] print statements
   - The automatic wrapper will handle detailed logging for the main API

3. GENERAL:
   - Keep log output concise but informative
   - Always log the outcome of lookups (found/not found)
   - Always log coordinates from geofence calls

2. CRITICAL PAYLOAD HANDLING (Multipart/DTO vs JSON):
   - CHECK if the API Step URL or Description implies a Multipart/DTO upload (vs standard JSON).
   - Signals: "Payload Type: DTO_FILE", "Multipart", "upload", "file".
   - IF MULTIPART/DTO:
     - ❌ STRICTLY FORBIDDEN: DO NOT use `json=payload` or `data=json.dumps(payload)`.
     - ❌ STRICTLY FORBIDDEN: DO NOT set `Content-Type: application/json` header manually.
     - ✅ MUST USE `files` parameter.
     - Code Pattern:
       ```python
       payload_data = { ... } # Construct dictionary
       # Wrap in Multipart 'dto' - CRITICAL STRUCTURE
       files = {
           'dto': (None, json.dumps(payload_data), 'application/json')
       }
       # Execute
       response = requests.post(url, headers={'Authorization': f'Bearer {builtins.token}'}, files=files)
       ```
   - IF STANDARD JSON:
     - Use `requests.post(url, json=payload, ...)`

3. CRITICAL SUCCESS CONDITION:
   - APIs may return 200 (OK) or 201 (Created) for success.
   - ALWAYS check `if response.ok:` or `if response.status_code in [200, 201]:`.
   - ❌ DO NOT check `if response.status_code == 200:` (This causes false failures for 201).

4. CRITICAL DATA VALIDATION - PHONE NUMBERS:
   - If the input description mentions 'Phone Number' or 'Mobile Number', YOU MUST ENFORCE STRICT FORMATTING.
   - The allowed format is exact: "91 9876543210" or "91-9876543210" (Country Code [space/hyphen] Mobile Number).
   - Validation Logic (Python):
     ```python
     phone_raw = str(row.get('Phone Number', '')).strip()
     if ' ' in phone_raw:
         parts = phone_raw.split(' ')
     elif '-' in phone_raw:
         parts = phone_raw.split('-')
     else:
         row['Result'] = 'Fail' # Or 'Status' based on script convention
         # CRITICAL: Use this EXACT error message format
         row['Response'] = 'Invalid phone number format. Required in 91 9876543210' 
         return row

     if len(parts) != 2:
         row['Result'] = 'Fail'
         row['Response'] = 'Invalid phone number format. Required in 91 9876543210'
         return row

     country_code = "+" + parts[0]
     mobile_number = parts[1]
     ```
   - Use `country_code` and `mobile_number` in your API payload.
   - Do NOT default to +91 if the format is wrong. FAIL THE ROW."""
    
    # Add thread_utils requirements if multithreaded
    if is_multithreaded:
        prompt += """\n\nCRITICAL THREAD_UTILS UPDATE:
1. FUNCTION SIGNATURE: process_row MUST be 'def process_row(row)' - takes ONLY row parameter.
2. ACCESSING TOKEN/ENV_CONFIG: Use builtins.token and builtins.env_config (injected by thread_utils).
3. RUN FUNCTION: return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)
4. IMPORT: Ensure 'import builtins' is at the top.
5. REMOVE any (row, token, env_config) signatures - use (row) only.
6. THREAD SAFETY: Use '_lock = thread_utils.create_lock()' for shared caches."""
    
    # ALWAYS add Master Search instructions - CRITICAL for any data lookup
    prompt += """\n\nCRITICAL MASTER SEARCH UPDATE:
🚨 FORBIDDEN: DO NOT write custom API calls for user, farmer, soiltype, irrigationtype, or any master data lookups.
You MUST use the master_search component for ALL master data lookups.

1. IMPORT: Ensure 'import components.master_search as master_search' is at the top
3. INITIALIZE CACHES (🚨 MODULE LEVEL ONLY - TOP OF SCRIPT):
   - ❌ WRONG: `def run(...): _soiltype_list = ...`
   - ✅ RIGHT: `_soiltype_list = ...` (at top of script)
   - _user_cache = {} for search mode, _soiltype_list = master_search.fetch_all('soiltype', builtins.env_config) for once mode
4. LOOKUP PATTERN (ONCE mode):
   ```python
   result = master_search.lookup_from_cache(_soiltype_list, 'name', row.get('SoilType'), 'id')
   ```
6. MANDATORY LOGIC REPLACEMENT (SEARCH mode - ALL MASTER TYPES):
   🚨 CRITICAL: This optimization applies to ALL search-mode master types (user, farmer, project, etc.)
   
   For EACH search-mode master type in your script, you MUST apply this bypass pattern:
   
   **STEP 1: Detect ID Column at Module Level**
   At the start of run() function, check if the first row has the ID column.
   The column name pattern is typically: '{MasterTypeName}_id' or '{OutputFieldName}'
   
   Examples:
   - For 'user' master → Check for 'UserID' or 'AssignedTo_id' column
   - For 'farmer' master → Check for 'Farmer Name_id' or 'FarmerID' column
   - For 'project' master → Check for 'Project_id' or 'ProjectID' column
   
   **STEP 2: Apply Conditional Logic in process_row()**
   
   ```python
   # EXAMPLE 1: User Master Type
   # At start of run() function (MODULE LEVEL):
   _use_provided_user_ids = bool(data and data[0].get('UserID'))
   
   # Inside process_row(row):
   if _use_provided_user_ids:
       # STRICT MODE: Use provided ID, fail if missing.
       user_id = row.get('UserID')
       if not user_id:
           row['Status'] = 'Fail'
           row['Response'] = 'UserID is empty (Strict Mode)'
           print(f"[USER_LOOKUP] {assigned_to_name} → ID: Not Found (Empty in Strict Mode)")
           return row
       print(f"[USER_LOOKUP] {assigned_to_name} → ID: {user_id} (Provided)")
   else:
       # FALLBACK MODE: Perform Search
       result = master_search.search('user', assigned_to_name, builtins.env_config, _user_cache)
       if not result['found']:
           row['Status'] = 'Fail'
           row['Response'] = result['message']
           return row
       user_id = result['value']
   
   # EXAMPLE 2: Farmer Master Type
   # At start of run() function (MODULE LEVEL):
   _use_provided_farmer_ids = bool(data and data[0].get('Farmer Name_id'))
   
   # Inside process_row(row):
   if _use_provided_farmer_ids:
       # STRICT MODE: Use provided ID, fail if missing.
       farmer_id = row.get('Farmer Name_id')
       if not farmer_id:
           row['Status'] = 'Fail'
           row['Response'] = 'Farmer Name_id is empty (Strict Mode)'
           print(f"[FARMER_LOOKUP] {farmer_name} → ID: Not Found (Empty in Strict Mode)")
           return row
       print(f"[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id} (Provided)")
   else:
       # FALLBACK MODE: Perform Search
       result = master_search.search('farmer', farmer_name, builtins.env_config, _farmer_cache)
       if not result['found']:
           row['Status'] = 'Fail'
           row['Response'] = result['message']
           return row
       farmer_id = result['value']
   ```
   
   🚨 CRITICAL RULES:
   - Apply this pattern to EVERY search-mode master in your script (user, farmer, project, etc.)
   - The bypass variable name should be: `_use_provided_{master_type}_ids`
   - ALWAYS add the print statement for logging whether ID was provided or searched
   - Initialize the bypass flag at the START of run() function, NOT inside process_row()
   
5. REMOVE any custom /services/user/api/users or /services/authorization API calls
6. REMOVE any requests.get() for user/farmer lookups - replace with master_search.search()
7. master_search handles: path variables, company_id injection, query parameters, caching"""

    # DYNAMIC PROMPT INJECTION FOR DTO
    if "DTO_FILE" in description or "multitype" in description.lower():
         prompt += "\n\n🚨🚨🚨 SPECIAL OVERRIDE: DTO_FILE PAYLOAD DETECTED 🚨🚨🚨"
         prompt += "\nOne of your API steps requires 'DTO_FILE'."
         prompt += "\nYou MUST use `requests.post(..., files={'dto': (None, json.dumps(payload), 'application/json')})`."
         prompt += "\nDO NOT use `json=payload`. This will fail the request."
         prompt += "\nThis is the MOST IMPORTANT requirement for this script."

    
    models = _get_applicable_models(api_key)
    success, content, err = _call_gemini_with_candidates(api_key, models, {"contents": [{"parts": [{"text": prompt}]}]})
    
    # Post-processing: Fix API key name for geofence operations (same as generate_script)
    if success and 'geofence_utils' in content:
        content = content.replace(
            "builtins.env_config.get('google_api_key')",
            "builtins.env_config.get('Geocoding_api_key')"
        )
        content = content.replace(
            'builtins.env_config.get("google_api_key")',
            'builtins.env_config.get("Geocoding_api_key")'
        )
        content = content.replace(
            "env_config.get('google_api_key')",
            "env_config.get('Geocoding_api_key')"
        )
        content = content.replace(
            'env_config.get("google_api_key")',
            'env_config.get("Geocoding_api_key")'
        )
    
    header = _get_ist_header('AI Updated')
    
    # [CONFIG INJECTION]
    header += f"\n# CONFIG: enableGeofencing = {str(enable_geofencing)}"
    header += f"\n# CONFIG: allowAdditionalAttributes = {str(allow_additional_attributes)}"
    
    if input_columns:
        col_str = ', '.join(input_columns) if isinstance(input_columns, list) else str(input_columns)
        header += f"\n# EXPECTED_INPUT_COLUMNS: {col_str}"

    return f"{header}\n{content}" if success else f"# update error: {err}\n# Original:\n{existing_code}"

if __name__ == "__main__":
    try:
        raw_data = sys.stdin.read()
        if not raw_data.strip():
            sys.exit(0)
        data = json.loads(raw_data)
        desc = data.get('generationPrompt', data.get('description', ''))
        ex_code = data.get('existing_code', '')
        cols = data.get('inputColumns', '')
        mt = data.get('isMultithreaded', True)
        attr = data.get('allowAdditionalAttributes', False)
        geo = data.get('enableGeofencing', False)
        out_conf = data.get('outputConfig', None)
        
        if ex_code: print(json.dumps({"status":"success", "script": update_script_with_ai(ex_code, desc, mt, cols, attr, geo, out_conf)}))
        else: print(json.dumps({"status":"success", "script": generate_script(desc, mt, cols, attr, geo, out_conf)}))
    except Exception as e:
        print(json.dumps({"status":"error", "message":str(e)}))
