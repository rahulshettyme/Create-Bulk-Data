import sys
import json
import os
import requests
import re
from typing import Dict, List, Any, Tuple

def sanitize_code(code: str) -> str:
    """Sanitizes sensitive information like JWT tokens from the code."""
    # Regex for JWT tokens (Header.Payload.Signature)
    # Heuristic: 3 parts separated by dots, base64url characters
    jwt_pattern = r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+'
    
    # Replace with a safe placeholder
    sanitized = re.sub(jwt_pattern, '"<REDACTED_ACCESS_TOKEN>"', code)
    return sanitized

def get_gemini_api_key():
    """Fetches Gemini API Key from Env Var or System/db.json"""
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if key: return key
    
    # 2. Try secrets.json (Local Development)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
        secrets_path = os.path.join(base_dir, "System", "secrets.json")
        if os.path.exists(secrets_path):
            with open(secrets_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                key = data.get("google_api_key", "").strip() or data.get("gemini_api_key", "").strip()
                if key: return key
    except: pass

    # 3. Fallback to db.json (Legacy)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
        db_path = os.path.join(base_dir, "System", "db.json")
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("gemini_api_key", "").strip()
    except: pass
    return ""

def extract_excel_columns(code: str) -> List[str]:
    """Extract Excel column names from code comments (Priority) or usage."""
    
    # 1. OPTION A: Look for explicit definition (Standard Format)
    # Format: # Excel Columns: Col1, Col2, Col3 OR # Excel Columns for Input/Processing: Col1, Col2
    explicit_match = re.search(r'#\s*Excel Columns(?:\s+for\s+Input/Processing)?:\s*(.*)', code, re.IGNORECASE)
    if explicit_match:
        raw_cols = explicit_match.group(1).strip()
        if raw_cols:
             # Strip leading/trailing whitespace from the whole string first
             raw_cols = raw_cols.strip()
             return [c.strip() for c in raw_cols.split(',') if c.strip()]

    # 2. OPTION B: Scan usage in code (Fallback)
    columns = []
    seen = set()
    
    # Look for row.get('ColumnName') or row['ColumnName'] patterns
    patterns = [
        r"row\.get\(['\"]([^'\"]+)['\"]",  # Matches row.get('Col', ...)
        r"row\[['\"]([^'\"]+)['\"]\]",    # Matches row['Col']
        # Support for row.iloc (infer name from variable assignment)
        r"(\w+)\s*=\s*(?:get_value\()?row\.iloc\[", 
        # Support for dict keys with iloc value
        r"['\"](\w+)['\"]\s*:\s*(?:get_value\()?row\.iloc\["
    ]
    
    all_matches = []
    
    for pattern in patterns:
        for match in re.finditer(pattern, code):
            # match.groups() contains the captured groups. We expect 1 group.
            if match.groups():
                col_name = match.group(1)
                all_matches.append((match.start(), col_name))
    
    # Sort matches by their position in the code
    all_matches.sort(key=lambda x: x[0])
    
    for _, col in all_matches:
        if col not in seen:
            seen.add(col)
            columns.append(col)
    
    return columns

def extract_script_name(code: str) -> str:
    """Extract script name from docstring or filename."""
    # Look for "Script Name:" in comments or docstrings
    match = re.search(r'Script Name:\s*([^\n]+)', code)
    if match:
        return match.group(1).strip()
    return "Unknown Script"

def extract_group_by_column(code: str) -> str:
    """Extract groupByColumn config from comments OR code patterns."""
    # 1. Config Comment (Priority)
    match = re.search(r'# CONFIG: groupByColumn=["\']([^"\']+)["\']', code)
    if match:
        return match.group(1).strip()
    
    # 2. Heuristic: Look for dictionary grouping pattern
    # Pattern: name = row.get('name') ... grouped_data[name]
    # We look for: row.get('COLUMN') ... grouped_data
    code_no_newlines = code.replace('\n', ' ')
    heuristic_match = re.search(r"row\.get\(['\"]([^'\"]+)['\"]\).*?grouped_data", code_no_newlines)
    if heuristic_match:
         return heuristic_match.group(1).strip()
         
    return ""

def extract_threading_config(code: str) -> dict:
    """Extract threading configs."""
    config = {}
    
    # isMultithreaded
    mt_match = re.search(r'# CONFIG: isMultithreaded=(True|False)', code, re.IGNORECASE)
    if mt_match:
        config['isMultithreaded'] = (mt_match.group(1).lower() == 'true')
        
    # batchSize
    bs_match = re.search(r'# CONFIG: batchSize=(\d+)', code)
    if bs_match:
        config['batchSize'] = int(bs_match.group(1))
        
    return config

def build_concise_prompt(code_content: str, excel_columns: List[str]) -> str:
    """Build a concise prompt that generates shorter output to avoid truncation."""
    
    return f"""Analyze this Python automation script and output a JSON workflow.

CODE:
```python
{code_content}
```

OUTPUT (JSON only, no markdown):
{{
  "scriptName": "Name",
  "description": "Brief description",
  "excelColumns": {excel_columns},
  "steps": [
    {{
      "type": "API",
      "apiName": "Step name",
      "method": "GET|POST|PUT",
      "endpoint": "/path",
      "payloadType": "JSON|QUERY|DTO_FILE",
      "payload": "Structure with paths: object.data.field = value",
      "response": "var",
      "instruction": "Action with exact paths like farmer_data['data']['tags']",
      "runOnce": true/false
    }},
    {{
      "type": "LOGIC",
      "apiName": "Name",
      "logic": "Brief logic description"
    }}
  ]
}}

CRITICAL:
- IGNORE authentication/token generation steps (handled globally)
- USE RELATIVE PATHS for endpoints (e.g. /services/..., NOT https://domain.com/...)
- DISTINGUISH between Mandatory Input Excel Columns and UI Output Columns.
- UI Output columns (like ID, Name, Status, Response) should NOT be listed in excelColumns if they are only for display and not required in the input file.
- Keep descriptions under 100 chars
- Output valid JSON only
"""

def build_enhanced_prompt(code_content: str, excel_columns: List[str]) -> str:
    """Build a detailed prompt for Gemini with examples and structure."""
    
    return f"""You are an expert Python Code Analyzer. Reverse engineer this automation script into workflow steps.

**INPUT CODE**:
```python
{code_content}
```

**OUTPUT FORMAT** (Valid JSON only, no markdown):
{{
  "scriptName": "Brief descriptive name",
  "description": "One sentence description",
  "excelColumns": {excel_columns},
  "uiColumns": ["ID", "Name", "Status", "Response"],
  "steps": [
    {{
      "type": "API",
      "apiName": "Step Name",
      "method": "GET|POST|PUT|DELETE",
      "endpoint": "/api/path",
      "payloadType": "JSON|QUERY|DTO_FILE|MULTIPART",
      "payload": "DETAILED structure with EXACT nesting paths",
      "response": "variable_name",
      "instruction": "What this step does with SPECIFIC attribute paths",
      "runOnce": true/false
    }},
    {{
      "type": "LOGIC",
      "apiName": "Logic Step Name",
      "logic": "Brief description with data transformation details"
    }}
  ]
}}

**CRITICAL REQUIREMENTS FOR PAYLOAD FIELD**:
1. For POST/PUT operations, specify EXACT nested structure using dot notation
2. Example: "data.tags = [tag_ids]" NOT just "tags = [tag_ids]"
3. Show the FULL path: "farmer_data['data']['tags']" or "payload.data.tags"
4. If updating nested attributes, show: "response_object.data.tags.append(new_tag_id)"
5. Include parent objects: "{{'data': {{'tags': [ids]}}}}" not just "{{'tags': [ids]}}"

**EXAMPLE FOR UPDATE OPERATIONS**:
WRONG: "payload": "tags: [5883653, 5883654]"
CORRECT: "payload": "Use complete response object. Update nested path: data.tags = [existing_tags, new_tag_id]"

WRONG: "instruction": "Add tag to farmer"
CORRECT: "instruction": "Fetch farmer object, update farmer_data['data']['tags'] array by appending tag_id, send complete farmer_data object"

**RULES**:
1. Output ONLY valid JSON (no markdown, no explanations)
2. Analyze the `process_row` or main processing function
3. Each API call = one API step
4. Each significant logic block = one LOGIC step
5. For payload, show EXACT attribute paths and nesting
6. For instructions, mention EXACT attribute locations like "data.tags", "address.locality"
7. Order steps by execution sequence
8. If payload modifies a fetched object, state: "Modify response from Step X at path Y"
9. Set "runOnce": true if the API call fetches Master Data (e.g. Crops, Soils) and should be cached/run only once.
10. DISTINGUISH Input vs Output:
    - "excelColumns": ONLY columns required for the INPUT Excel file.
    - "uiColumns": Columns purely for display in the UI result table (e.g., 'ID', 'Name', 'Status', 'Response'). If a column (like 'CA_ID') is both an input AND used for display title, list it in BOTH.

Start analysis:
"""

def _call_gemini_with_candidates(api_key: str, models_to_try: List[str], 
                                  payload: Dict) -> Tuple[bool, Any, str]:
    """Helper to try multiple models with retries."""
    import time
    last_error = "No models tried"
    
    for model in models_to_try:
        # Use v1beta API for generateContent
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        # Retry loop (3 attempts)
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=120)
                
                if resp.status_code == 200:
                    result = resp.json()
                    if 'candidates' in result and result['candidates']:
                        candidate = result['candidates'][0]
                        
                        # Check if response was truncated due to length or safety
                        finish_reason = candidate.get('finishReason', 'UNKNOWN')
                        if finish_reason not in ['STOP', 'MAX_TOKENS']:
                            last_error = f"Model {model} stopped unexpectedly: {finish_reason}"
                            break
                        
                        generated_text = candidate['content']['parts'][0]['text']
                        
                        # Clean markdown
                        if "```json" in generated_text:
                            generated_text = generated_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in generated_text:
                            generated_text = generated_text.split("```")[1].split("```")[0].strip()
                        
                        # Log warning if truncated
                        if finish_reason == 'MAX_TOKENS':
                            print(f"Warning: Response from {model} was truncated due to max tokens", file=sys.stderr)
                            
                        return True, generated_text.strip(), None
                    else:
                        last_error = f"Model {model} returned no content (possible safety filter)"
                        break
                        
                elif resp.status_code == 503 or resp.status_code == 429:
                    # Overloaded or Rate Limited, retry with backoff
                    last_error = f"Model {model} failed with {resp.status_code} (Retries exhausted)"
                    
                    sleep_time = 2 * (attempt + 1)
                    if resp.status_code == 429:
                        sleep_time += 2 # Extra padding for quota
                    time.sleep(sleep_time)
                    continue
                    
                elif resp.status_code == 404:
                    last_error = f"Model {model} not found (404). Trying next model..."
                    break  # Try next model
                    
                else:
                    last_error = f"Model {model} failed with {resp.status_code}: {resp.text[:200]}"
                    break 
                    
            except requests.exceptions.Timeout:
                last_error = f"Model {model} timeout on attempt {attempt + 1}"
                time.sleep(1)
                
            except Exception as e:
                last_error = f"Model {model} exception: {str(e)}"
                time.sleep(1)

    return False, None, last_error

def extract_payload_structure(code: str, step_context: str = "") -> str:
    """Analyze code to extract specific payload structure modifications."""
    
    # Look for nested dictionary assignments
    nested_patterns = [
        r"(\w+)\['([^']+)'\]\['([^']+)'\]\s*=",  # obj['data']['tags'] =
        r"(\w+)\.(\w+)\.(\w+)\s*=",  # obj.data.tags =
        r"if\s+'([^']+)'\s+not\s+in\s+(\w+):\s*(\w+)\['([^']+)'\]\s*=",  # if 'data' not in obj: obj['data'] =
    ]
    
    structures = []
    for pattern in nested_patterns:
        matches = re.findall(pattern, code)
        for match in matches:
            if len(match) >= 3:
                structures.append(f"{match[0]}.{match[1]}.{match[2]}")
    
    # Look for array operations
    array_patterns = [
        r"(\w+)\['([^']+)'\]\['([^']+)'\]\.append",  # obj['data']['tags'].append
        r"(\w+)\.get\('([^']+)',\s*\[\]\)",  # obj.get('tags', [])
    ]
    
    for pattern in array_patterns:
        matches = re.findall(pattern, code)
        for match in matches:
            if len(match) >= 2:
                structures.append(f"{match[0]}.{match[1]} (array)")
    
    return " | ".join(set(structures)) if structures else ""

def enhance_step_with_structure(step: Dict, code_content: str) -> Dict:
    """Enhance a step with structural information extracted from code."""
    
    if step.get("type") != "API":
        return step
    
    method = step.get("method", "").upper()
    endpoint = step.get("endpoint", "")
    
    # For PUT/POST, try to find the exact payload construction
    if method in ["PUT", "POST", "PATCH"]:
        # Search for the code section related to this endpoint
        endpoint_pattern = re.escape(endpoint.split('?')[0].split('{')[0])
        
        # Find code blocks near this endpoint
        code_lines = code_content.split('\n')
        context_lines = []
        
        for i, line in enumerate(code_lines):
            if endpoint_pattern in line or method.lower() in line.lower():
                # Get surrounding context (10 lines before and after)
                start = max(0, i - 10)
                end = min(len(code_lines), i + 15)
                context_lines = code_lines[start:end]
                break
        
        context_code = '\n'.join(context_lines)
        
        # Extract structure
        structure_info = extract_payload_structure(context_code)
        
        # Enhance payload description with structure
        if structure_info and step.get("payload"):
            current_payload = step["payload"]
            if "data.tags" not in current_payload and "data" in structure_info:
                step["payload"] = f"{current_payload} | Structure: Updates nested {structure_info}"
        
        # Enhance instructions with specific paths
        if step.get("instruction"):
            # Look for dictionary path patterns in context
            dict_paths = re.findall(r"(\w+)\['([^']+)'\]\['([^']+)'\]", context_code)
            if dict_paths:
                paths_str = ", ".join([f"{p[0]}.{p[1]}.{p[2]}" for p in dict_paths[:3]])
                if paths_str not in step["instruction"]:
                    step["instruction"] = f"{step['instruction']} [Modifies: {paths_str}]"
    
    return step

def normalize_steps(steps: List[Dict], code_content: str = "") -> List[Dict]:
    """Ensure steps match the UI structure exactly and enhance with code analysis."""
    valid_steps = []
    
    for i, s in enumerate(steps):
        step = {
            "type": s.get("type", "LOGIC").upper(),
            "apiName": s.get("apiName", f"Step {i+1}"),
            "method": s.get("method", "GET").upper() if s.get("type", "").upper() == "API" else "",
            "endpoint": s.get("endpoint", ""),
            "payloadType": s.get("payloadType", "JSON"),
            "payload": s.get("payload", ""),
            "response": s.get("response", ""),
            "runOnce": s.get("runOnce", False),
            "instruction": s.get("instruction", ""),
            "logic": s.get("logic", "")
        }
        
        # Cleanup based on type
        if step["type"] == "API":
            # FILTER: Skip Authentication/Token steps
            name_lower = step["apiName"].lower()
            endpoint_lower = step["endpoint"].lower()
            if "token" in name_lower or "auth" in name_lower or "login" in name_lower or "get_access_token" in name_lower:
                continue
            
            # CLEANER: Strip Hardcoded Domain (keep relative path)
            if step["endpoint"] and step["endpoint"].startswith("http"):
                step["endpoint"] = re.sub(r'^https?://[^/]+', '', step["endpoint"])

            if not step["endpoint"]:
                step["endpoint"] = "/unknown"
            if not step["instruction"]:
                step["instruction"] = f"Execute {step['method']} request to {step['endpoint']}"
            
            # Enhance with structural information from code
            if code_content:
                step = enhance_step_with_structure(step, code_content)
                
        elif step["type"] == "LOGIC":
            if not step["logic"]:
                step["logic"] = step.get("instruction", "Processing step")
            # Clear API-specific fields for LOGIC steps
            step["method"] = ""
            step["endpoint"] = ""
            step["payloadType"] = ""
            step["payload"] = ""
            step["response"] = ""
             
        valid_steps.append(step)
        
    return valid_steps

def reverse_engineer_script(code_content: str) -> Dict[str, Any]:
    """Analyzes Python code using Gemini to reverse-engineer steps."""
    
    api_key = get_gemini_api_key()
    if not api_key:
        return {"error": "No GOOGLE_API_KEY found in environment/db.json"}

    # Extract metadata from code
    excel_columns = extract_excel_columns(code_content)
    script_name = extract_script_name(code_content)
    
    # Try multiple models in order of preference (using available models)
    models_to_try = [
        "gemini-2.5-flash",      # Fast and efficient
        "gemini-2.5-pro",         # More capable
        "gemini-2.0-flash-exp",   # Experimental but fast
        "gemini-flash-latest"     # Fallback
    ]

    # Use concise prompt to avoid truncation
    # SANITIZATION: Remove tokens before sending to AI
    sanitized_code = sanitize_code(code_content)
    prompt = build_concise_prompt(sanitized_code, excel_columns)
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,  # Lower temperature for more consistent output
            "maxOutputTokens": 16000,  # Increased for longer responses
            "topP": 0.8,
            "topK": 40
        }
    }
    
    success, content, last_error = _call_gemini_with_candidates(api_key, models_to_try, payload)

    if success:
        try:
            # Try to extract JSON from the response
            json_content = content
            
            # If content is incomplete, it might be cut off - try to find complete JSON
            if content and not content.rstrip().endswith('}'):
                # Response was truncated
                print(f"Warning: Response appears truncated. Length: {len(content)}", file=sys.stderr)
                # Try to find the last complete bracket
                last_brace = content.rfind('}')
                if last_brace > 0:
                    # Check if we can find a complete steps array
                    last_bracket = content.rfind(']', 0, last_brace)
                    if last_bracket > 0:
                        # Try to construct a valid JSON by closing it properly
                        json_content = content[:last_bracket+1] + '\n  ]\n}'
                        print(f"Attempting to recover truncated JSON...", file=sys.stderr)
                
            data = json.loads(json_content)
            
            # Handle both formats: {"steps": [...]} or direct [...]
            if isinstance(data, list):
                steps = data
                # Extract configs
                threading_conf = extract_threading_config(code_content)
                group_col = extract_group_by_column(code_content)
                
                # Build enhanced description
                desc_text = f"Automation script: {script_name}"
                config_info = []
                if group_col:
                    config_info.append(f"- Group By: {group_col}")
                if threading_conf.get('isMultithreaded') is not None:
                    status = "Enabled" if threading_conf['isMultithreaded'] else "Disabled"
                    config_info.append(f"- Multithreading: {status}")
                if threading_conf.get('batchSize'):
                    config_info.append(f"- Batch Size: {threading_conf['batchSize']}")
                
                if config_info:
                    desc_text += "\n\n### ⚙️ Configuration\n" + "\n".join(config_info)

                result = {
                    "scriptName": script_name,
                    "description": desc_text,
                    "excelColumns": excel_columns,
                    "groupByColumn": group_col,
                    "isMultithreaded": threading_conf.get('isMultithreaded'),
                    "batchSize": threading_conf.get('batchSize'),
                    "steps": normalize_steps(steps, code_content)
                }
            elif "steps" in data:
                result = {
                    "scriptName": data.get("scriptName", script_name),
                    "description": data.get("description", f"Automation script: {script_name}"),
                    "excelColumns": data.get("excelColumns", excel_columns),
                    "steps": normalize_steps(data["steps"], code_content)
                }
            else:
                return {
                    "error": "Invalid response format from AI",
                    "raw": content[:1000]
                }
                
            return result
            
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse AI response as JSON: {str(e)}",
                "raw": content[:2000],  # Show more of the response
                "full_length": len(content)
            }
        except Exception as e:
            return {
                "error": f"Processing error: {str(e)}",
                "raw": content[:1000]
            }
    
    return {"error": f"AI Generation Failed: {last_error}"}

def main():
    """Main entry point for the script."""
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"error": "No input provided"}))
            sys.exit(1)
            
        req = json.loads(input_data)
        code = req.get('code', '')
        
        if not code:
            print(json.dumps({"error": "No code provided in request"}))
            sys.exit(1)
        
        result = reverse_engineer_script(code)
        
        print("---JSON_START---")
        print(json.dumps(result, indent=2))
        
    except json.JSONDecodeError as e:
        print("---JSON_START---")
        print(json.dumps({"error": f"Invalid JSON input: {str(e)}"}))
        
    except Exception as e:
        print("---JSON_START---")
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}))

if __name__ == "__main__":
    main()