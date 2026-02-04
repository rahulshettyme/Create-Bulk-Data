
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
    if is_multithreaded: import_ins.append("thread_utils")
    if enable_geofencing: import_ins.append("geofence_utils")
    if allow_additional_attributes: import_ins.append("attribute_utils")
    
    col_req = f"\n    CRITICAL - INPUT COLUMNS: {input_columns}" if input_columns else ""
    run_req = "return thread_utils.run_in_parallel(process_func=process_row, items=data)" if is_multithreaded else "execute sequentially by iterating data"

    prompt = f"You are a Python expert. Description: {description}. {col_req}. Requirements: def run(data, token, env_config), import {', '.join(import_ins)}. {run_req}."
    if allow_additional_attributes: prompt += "\nUse attribute_utils.add_attributes_to_payload(row, payload, env_config)."
    if enable_geofencing: prompt += "\nCRITICAL REQUIREMENT: Dynamic Geofencing is ENABLED. You MUST import geofence_utils and use 'geofence_utils.check_geofence(lat, lon, env_config.get('targetLocation'), env_config.get('google_api_key'), cache=geo_cache)' to validate coordinates. Do NOT use hardcoded polygons. Do NOT fallback to simplified logic. Trust that geofence_utils is available."
    
    if output_config and output_config.get('isDynamicUI'):
        ui_mapping = output_config.get('uiMapping', [])
        prompt += "\n\nCRITICAL OUTPUT REQUIREMENT: The script logic MUST populate the output 'row' dictionary with the following keys exactly as specified:"
        for m in ui_mapping:
             prompt += f"\n- Key '{m['colName']}': {m['logic']} (Source Value: {m['value']})"
        prompt += "\nEnsure these keys exist in the 'row' dictionary returned by process_row. Do not output 'Name', 'Code', 'Response' unless explicitly asked."

    prompt += "\nCRITICAL: DO NOT add any print statements for debugging API requests (e.g. [API_DEBUG]). The system automatically logs all requests."

    models = _get_applicable_models(api_key)
    success, content, err = _call_gemini_with_candidates(api_key, models, {"contents": [{"parts": [{"text": prompt}]}]})
    return f"{_get_ist_header('AI Generated')}\n{content}" if success else f"# error: {err}\n{generate_heuristic_script(description)}"

def update_script_with_ai(existing_code, description, is_multithreaded=True, input_columns=None, allow_additional_attributes=False, enable_geofencing=False, output_config=None):
    api_key = get_gemini_api_key()
    if not api_key: return "# API Key missing"
    
    code = sanitize_code(clean_ai_headers(existing_code))
    prompt = f"Refactor this code to match the NEW description exactly.\n\nNEW DESCRIPTION:\n{description}\n\nEXISTING CODE:\n```python\n{code}\n```\n\nCRITICAL INSTRUCTIONS:\n1. The Description is the SOURCE OF TRUTH. Steps in the code that are NOT in the description MUST be REMOVED.\n2. Specifically, if an API call or logic block exists in the code but is not mentioned in the description, DELETE IT.\n3. Preserve helper functions, imports, and error handling.\n4. Update variable references as needed."
    prompt += "\n\nCRITICAL BEST PRACTICES:\n- Robust JSON Parsing: API responses might be a list `[...]` or a dict `{'data': [...]}`. Handle both cases. Example: `data = resp.json(); items = data if isinstance(data, list) else data.get('data', [])`\n- Robust String Matching: ALWAYS `.strip()` and `.lower()` when comparing strings (e.g. from Excel vs API) to avoid whitespace mismatches.\n- Error Handling: Do NOT use empty `except: pass`. Print error messages if setup steps fail."
    if allow_additional_attributes: prompt += "\nEnsure attribute_utils is used."
    if enable_geofencing: prompt += "\nCRITICAL UPDATE: Dynamic Geofencing is ENABLED. Replace any existing hardcoded polygon logic (e.g. INDIA_POLY) with 'geofence_utils.check_geofence(lat, lon, env_config.get('targetLocation'), env_config.get('google_api_key'), cache=geo_cache)'. Ensure 'geofence_utils' is imported."
    
    if output_config and output_config.get('isDynamicUI'):
        ui_mapping = output_config.get('uiMapping', [])
        prompt += "\n\nCRITICAL OUTPUT REQUIREMENT: Ensure the script produces a dictionary (row) with the following keys:"
        for m in ui_mapping:
             prompt += f"\n- '{m['colName']}': {m['logic']} (Source: {m['value']})"
             
    prompt += "\nCRITICAL: REMOVE any manual print statements for [API_DEBUG]. The system handles this automatically."

    models = _get_applicable_models(api_key)
    success, content, err = _call_gemini_with_candidates(api_key, models, {"contents": [{"parts": [{"text": prompt}]}]})
    return f"{_get_ist_header('AI Updated')}\n{content}" if success else f"# update error: {err}\n# Original:\n{existing_code}"

if __name__ == "__main__":
    try:
        raw_data = sys.stdin.read()
        if not raw_data.strip():
            sys.exit(0)
        data = json.loads(raw_data)
        desc = data.get('description', '')
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
