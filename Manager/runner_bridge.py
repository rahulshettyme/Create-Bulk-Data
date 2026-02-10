import sys
import json
import argparse
import importlib.util
import os
import traceback
import io
import builtins
import datetime

# Force UTF-8 for stdout/stderr to avoid charmap errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_script(target_script, data, token, env_config_json):
    # FILE LOGGING FOR DEBUGGING
    try:
        debug_path = os.path.join(os.path.dirname(target_script), 'runner_debug.txt')
        with open(debug_path, 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.datetime.now()}] Runner Started for {os.path.basename(target_script)}\n")
    except: pass

    print("DEBUG: Runner Loaded", flush=True)
    print(f"DEBUG: ARGS: {sys.argv}", flush=True)

    try:
        # 1. Parse Inputs
        # data is already a list/dict passed from main
        env_config = json.loads(env_config_json)
        
        # Initialize API keys
        geocoding_key = None
        gemini_key = None
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Load secrets/db to find keys AND master_data_config
        try:
            for filename in ["System/secrets.json", "System/db.json"]:
                path = os.path.join(base_dir, filename)
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data_json = json.load(f)
                        
                        # Read keys if not already found
                        if not geocoding_key:
                            geocoding_key = data_json.get("Geocoding_api_key", "").strip()
                        
                        if not gemini_key:
                            gemini_key = data_json.get("google_api_key", "").strip() or data_json.get("gemini_api_key", "").strip()
                        
                        # ALWAYS load master_data_config if missing
                        if "master_data_config" in data_json and "master_data_config" not in env_config:
                            env_config["master_data_config"] = data_json["master_data_config"]
                            print("DEBUG: Loaded master_data_config from file", flush=True)
                        
                        # We continue loop to ensure we find master_data_config even if keys found in first file
        except: pass
        
        # Assign found keys to env_config
        if geocoding_key and 'Geocoding_api_key' not in env_config:
            env_config['Geocoding_api_key'] = geocoding_key
            
        if gemini_key and 'google_api_key' not in env_config:
            env_config['google_api_key'] = gemini_key
            
    except Exception as e:
        print(f"Warning: Failed to load secrets: {e}")
        
    # 2. Load User Script
    script_dir = os.path.dirname(target_script)
    if script_dir not in sys.path:
        sys.path.append(script_dir)

    # Fix for Import Errors: Add project root and 'components' directory to sys.path
    # This allows scripts to do `import attribute_utils` or `from components import ...`
    manager_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(manager_dir)
    components_dir = os.path.join(project_root, 'components')
    
    if project_root not in sys.path:
        sys.path.append(project_root)
    if components_dir not in sys.path:
        sys.path.append(components_dir)

    # NEW: Add 'Converted Scripts' to path so draft scripts can find thread_utils/attribute_utils
    converted_scripts_dir = os.path.join(project_root, 'Converted Scripts')
    if converted_scripts_dir not in sys.path:
        sys.path.append(converted_scripts_dir)

    spec = importlib.util.spec_from_file_location("user_module", target_script)
    if not spec or not spec.loader:
        raise FileNotFoundError(f"Could not load script: {target_script}")
        
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # 3. Check for run function
    if not hasattr(module, "run"):
         raise AttributeError("Script is missing 'run(data, token, env_config)' function.")
         
    # 4. Execute
    try:
        # CLEANUP: Remove stale output file from previous runs
        excel_out_path = os.path.join(os.getcwd(), 'Uploaded_File.xlsx')
        if os.path.exists(excel_out_path):
            try:
                os.remove(excel_out_path)
                print("DEBUG: Cleaned up stale Uploaded_File.xlsx")
            except Exception as e:
                print(f"DEBUG: Failed to remove stale Excel: {e}")

        # Run the script
        results = module.run(data, token, env_config)

        # 4b. CHECK FOR EXCEL OUTPUT AND DUMP
        # 4b. CHECK FOR EXCEL OUTPUT AND DUMP
        if os.path.exists(excel_out_path):
            try:
                import pandas as pd
                # Read it back to dump as JSON for frontend download
                df_out = pd.read_excel(excel_out_path, engine='openpyxl')
                print("\n[OUTPUT_DATA_DUMP]")
                print(df_out.to_json(orient='records', date_format='iso'))
                print("[/OUTPUT_DATA_DUMP]")
            except Exception as e:
                print(f"DEBUG: Failed to dump excel output: {e}")
        elif isinstance(results, list) and len(results) > 0:
            # NEW: Support for in-memory results (Unified Script Flow)
            # If script returns list but no file, dump the list directly.
            try:
                import pandas as pd
                df_out = pd.DataFrame(results)
                
                # REORDERING LOGIC RESTORED
                if hasattr(builtins, 'output_columns') and builtins.output_columns:
                    desired_order = []
                    for c in builtins.output_columns:
                        if isinstance(c, dict) and 'colName' in c:
                            desired_order.append(c['colName'])
                        else:
                            desired_order.append(str(c))
                    
                    # 1. Identify columns that are in the dataframe but NOT in the desired order (extra columns)
                    existing_cols = df_out.columns.tolist()
                    extra_cols = [c for c in existing_cols if c not in desired_order]
                    
                    # 2. Identify columns that are in the desired order but MISSING from dataframe
                    # (Optional: we could add them as empty, but pandas reindex handles this with NaN)
                    
                    # 3. Construct final order: Desired Columns + Extra Columns
                    # Filter desired_order to only include those that actually exist (or let reindex add NaNs)
                    # We usually want to force the desired structure, so we keep all desired_order.
                    final_order = desired_order + extra_cols
                    
                    # 4. Reindex the dataframe
                    # Using reindex will add NaNs for missing desired columns, which is good behavior
                    df_out = df_out.reindex(columns=final_order)

                print("\n[OUTPUT_DATA_DUMP]")
                print(df_out.to_json(orient='records', date_format='iso'))
                print("[/OUTPUT_DATA_DUMP]")
            except Exception as e:
                print(f"DEBUG: Failed to dump in-memory results: {e}")
        
        # 4a. Capture data_df if it exists (Legacy Support)
        # The script converter injects 'data_df' into the global scope of the module?
        # No, 'data_df' is local to 'run' function in the converted script.
        # Local vars in 'run' are NOT accessible on 'module' object.
        # CRITICAL: The converter must MAKE 'data_df' global or return it.
        # The user's script uses 'data_df' as a local var.
        # I must update the CONVERTER to return `data_df` at the end of `run`.
        
        # WAIT. I cannot access local variables of a function from outside in Python easily.
        # I must update script_converter.py to add `return data_df` at the end of `run`.
        
        # Reverting this thought: I will not edit runner_bridge yet.
        # I must go back to script_converter.py

        
        # Output strictly structured JSON with delimiter
        output = {
            "status": "success",
            "data": results
        }
        print("\n---JSON_START---")
        print(json.dumps(output, default=str)) # No indent for compactness

    except BaseException as e:
        err_output = {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        # LOG ERROR TO FILE
        try:
            debug_path = os.path.join(os.path.dirname(target_script), 'runner_debug.txt')
            with open(debug_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.datetime.now()}] ERROR: {str(e)}\n{traceback.format_exc()}\n")
        except: pass

        print("\n---JSON_START---")
        print(json.dumps(err_output, default=str))
        sys.exit(1) # Exit with error code
    
    except BaseException as e:
        # Capture full traceback for initial setup errors (parsing, loading, etc.)
        tb = traceback.format_exc()
        err_output = {
            "status": "error",
            "message": str(e),
            "traceback": tb
        }
        # LOG ERROR TO FILE
        try:
            debug_path = os.path.join(os.path.dirname(target_script), 'runner_debug.txt')
            with open(debug_path, 'a', encoding='utf-8') as f:
                 f.write(f"\n[{datetime.datetime.now()}] CRITICAL ERROR: {str(e)}\n{tb}\n")
        except: pass

        print("\n---JSON_START---")
        print(json.dumps(err_output, default=str))
        sys.exit(1) # Exit with error code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, help="Path to user .py script")
    parser.add_argument("--data", help="JSON string of rows") # Made optional
    parser.add_argument("--data-file", help="Path to JSON file containing rows") # New argument
    parser.add_argument("--token", help="Bearer Token")
    parser.add_argument("--env", help="Env Config JSON")
    parser.add_argument("--columns", help="Output Columns List JSON")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Load Data
    data = []
    if args.data_file and os.path.exists(args.data_file):
        try:
            with open(args.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Failed to read data file: {str(e)}"}))
            sys.exit(1)
    elif args.data:
        data = json.loads(args.data)
    else:
        # It's possible to run with empty data (though unlikely for this use case)
        data = []

    env_config = json.loads(args.env) if args.env else {}
    if args.token and 'token' not in env_config:
        env_config['token'] = args.token
    output_columns = json.loads(args.columns) if args.columns else []

    # Inject builtins
    builtins.data = data
    builtins.token = args.token
    builtins.env_config = env_config
    builtins.output_columns = output_columns
    builtins.DEBUG_MODE = args.debug # Set global debug flag
    
    # [MONKEY-PATCH] Global API Interceptor & Debug Logging
    try:
        import sys
        import os
        # Ensure project root is in sys.path for component imports
        # runner_bridge.py is in Manager/, so root is ../
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        import requests
        from components import attribute_utils
        
        # Determine if we should automate attribute injection
        auto_inject = env_config.get('allowAdditionalAttributes', False)
        print(f"DEBUG: API Interceptor Setup. Auto-Inject: {auto_inject}", flush=True)
        print(f"DEBUG: Env Config Keys: {list(env_config.keys())}", flush=True)
        if auto_inject:
             print(f"DEBUG: Additional Attributes Configured: {env_config.get('additionalAttributes', [])}", flush=True)
        
        original_request = requests.Session.request
        
        def intercepted_request(self, method, url, *args, **kwargs):
            # 1. Debug logging if enabled
            if getattr(builtins, 'DEBUG_MODE', False) or auto_inject: # Force logs if injection active
                 print(f"\n[INTERCEPTOR] Catching: {method} {url}", flush=True)
                 if 'json' in kwargs:
                     print(f"[INTERCEPTOR] Original Payload (JSON): {json.dumps(kwargs['json'])}", flush=True)
                 elif 'files' in kwargs and 'dto' in kwargs['files']:
                     print(f"[INTERCEPTOR] Original Payload (DTO): {kwargs['files']['dto'][1][:500]}...", flush=True)

            # 2. GLOBAL ATTRIBUTE INJECTION
            if auto_inject:
                row = attribute_utils.get_current_row()
                print(f"[INTERCEPTOR] Current Row Context Keys: {list(row.keys()) if row else 'None'}", flush=True)
                if row:
                    # Case A: JSON Payload
                    if 'json' in kwargs and kwargs['json']:
                        target_key = 'data' if 'data' in kwargs['json'] else None
                        attribute_utils.add_attributes_to_payload(row, kwargs['json'], env_config, target_key=target_key)
                        if getattr(builtins, 'DEBUG_MODE', False):
                             print(f"[INTERCEPTOR] Injected Attributes into JSON. Keys now: {list(kwargs['json'].get('data', kwargs['json']).keys())}", flush=True)
                    
                    # Case B: DTO Payload (multipart/form-data)
                    elif 'files' in kwargs and 'dto' in kwargs['files']:
                        dto_entry = kwargs['files']['dto']
                        if isinstance(dto_entry, tuple) and len(dto_entry) >= 2:
                            try:
                                dto_json = json.loads(dto_entry[1])
                                target_key = 'data' if 'data' in dto_json else None
                                attribute_utils.add_attributes_to_payload(row, dto_json, env_config, target_key=target_key)
                                
                                # Re-package the DTO
                                new_dto_content = json.dumps(dto_json)
                                new_list = list(dto_entry)
                                new_list[1] = new_dto_content
                                kwargs['files']['dto'] = tuple(new_list)
                                if getattr(builtins, 'DEBUG_MODE', False):
                                     print(f"[INTERCEPTOR] Injected Attributes into DTO. Keys now: {list(dto_json.get('data', dto_json).keys())}", flush=True)
                            except: pass
                else:
                    if getattr(builtins, 'DEBUG_MODE', False):
                        print("[INTERCEPTOR] Warning: Current Row Context is MISSING!", flush=True)
            
            # 3. Execute original
            response = original_request(self, method, url, *args, **kwargs)
            
            # 4. Debug response logging
            if getattr(builtins, 'DEBUG_MODE', False):
                print(f"[INTERCEPTOR] Response Status: {response.status_code}", flush=True)
                try:
                    preview = response.text[:1000] if response.text else ""
                    print(f"[INTERCEPTOR] Response Body: {preview}", flush=True)
                except: pass
                    
            return response

        requests.Session.request = intercepted_request
        print(f"DEBUG: API Interceptor Active.", flush=True)
    except Exception as e:
        print(f"DEBUG: Failed to setup API interceptor: {e}", flush=True)

    run_script(args.script, data, args.token, json.dumps(env_config))
