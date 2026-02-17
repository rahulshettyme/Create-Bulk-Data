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

def load_config_and_secrets(env_config):
    """
    Loads secrets/db and injects keys into env_config.
    """
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
    except Exception as e:
        print(f"Warning: Failed to load secrets: {e}")
        
    # Assign found keys to env_config
    if geocoding_key and 'Geocoding_api_key' not in env_config:
        env_config['Geocoding_api_key'] = geocoding_key
        
    if gemini_key and 'google_api_key' not in env_config:
        env_config['google_api_key'] = gemini_key
    
    return env_config

def run_script(target_script, data, token, env_config):
    # FILE LOGGING FOR DEBUGGING
    try:
        debug_path = os.path.join(os.path.dirname(target_script), 'runner_debug.txt')
        with open(debug_path, 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.datetime.now()}] Runner Started for {os.path.basename(target_script)}\n")
    except: pass

    print("DEBUG: Runner Loaded", flush=True)

    # env_config is now passed as a fully loaded dict from __main__
        
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

    def truncate_str(s, max_len=100):
        if not s: return s
        return (s[:max_len] + '...') if len(s) > max_len else s

    # 1. Load Initial Data
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

    # 2. Load Env Config & Secrets IMMEDIATELY
    env_config = json.loads(args.env) if args.env else {}
    if args.token and 'token' not in env_config:
        env_config['token'] = args.token
    
    # Load secrets/db BEFORE interceptor setup or builtin injection
    env_config = load_config_and_secrets(env_config)
    
    output_columns = json.loads(args.columns) if args.columns else []

    # 3. Inject builtins (Global and Complete Config)
    builtins.data = data
    builtins.token = args.token
    builtins.env_config = env_config
    builtins.output_columns = output_columns
    builtins.DEBUG_MODE = args.debug # Set global debug flag
    
    # Pretty-print ARGS for display (Smart Masking)
    display_args = []
    
    # We iterate manually to handle flag + value pairs
    i = 0
    raw_args = sys.argv
    while i < len(raw_args):
        arg = raw_args[i]
        
        if arg == '--token':
            display_args.append('--token')
            display_args.append('[SECRET_TOKEN]')
            i += 1
        elif arg == '--data':
            display_args.append('--data')
            try:
                row_count = len(json.loads(raw_args[i+1]))
                display_args.append(f'[JSON_DATA: {row_count} rows]')
            except: display_args.append('[JSON_DATA: Error parsing]')
            i += 1
        elif arg == '--env':
            display_args.append('--env')
            try:
                env_obj = json.loads(raw_args[i+1])
                env_name = env_obj.get('environment', 'Unknown')
                master_count = len(env_obj.get('master_data_config', {}))
                display_args.append(f'[ENV: {env_name}, Master Data System: {master_count} types available]')
            except: display_args.append('[ENV: Error parsing]')
            i += 1
        elif arg == '--columns':
            display_args.append('--columns')
            try:
                cols = json.loads(raw_args[i+1])
                display_args.append(f'[COLUMNS: {len(cols)}]')
            except: display_args.append('[COLUMNS: Error parsing]')
            i += 1
        else:
            # For other args (like --script), use standard truncation
            display_args.append(truncate_str(arg, 150))
            
        i += 1
    
    print("\n" + "="*60)
    print(f"🚀 RUNNER STARTING: {os.path.basename(args.script)}")
    print(f"📅 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📝 Args: {' '.join(display_args)}")
    print("="*60 + "\n")
    
    
    # [MONKEY-PATCH] Global API Interceptor & Debug Logging
    print("⚙️  Initializing API Interceptor...", flush=True)
    try:
        import sys
        import os
        # Ensure project root is in sys.path for component imports
        # runner_bridge.py is in Manager/, so root is ../
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        print("⚙️  Importing requests module...", flush=True)
        import requests
        
        print("⚙️  Importing attribute_utils...", flush=True)
        try:
            from components import attribute_utils
            print("✅ attribute_utils imported successfully", flush=True)
        except ImportError as e:
            print(f"⚠️  Warning: Could not import attribute_utils: {e}", flush=True)
            print("⚠️  Continuing without attribute injection support", flush=True)
            # Set a flag to skip interceptor setup
            attribute_utils = None
        
        # Determine if we should automate attribute injection
        auto_inject = env_config.get('allowAdditionalAttributes', False) and attribute_utils is not None
        print(f"⚙️  API Interceptor Setup. Auto-Inject: {auto_inject}", flush=True)
        
        if attribute_utils is not None:
            original_request = requests.Session.request
            
            def intercepted_request(self, method, url, *args, **kwargs):
                # 1. Debug logging if enabled
                if getattr(builtins, 'DEBUG_MODE', False) or auto_inject: # Force logs if injection active
                     print(f"\n📡 [INTERCEPTOR] {method.upper()} {url}", flush=True)

                # 2. GLOBAL ATTRIBUTE INJECTION
                if auto_inject:
                    row = attribute_utils.get_current_row()
                    if row:
                        # Case A: JSON Payload
                        if kwargs.get('json'):
                            target_key = 'data'
                            attribute_utils.add_attributes_to_payload(row, kwargs['json'], env_config, target_key=target_key)
                            if getattr(builtins, 'DEBUG_MODE', False):
                                 print(f"   ✨ Injected Attributes into JSON.", flush=True)
                        
                        # Case B: DTO Payload (multipart/form-data)
                        elif 'files' in kwargs and 'dto' in kwargs['files']:
                            dto_entry = kwargs['files']['dto']
                            if isinstance(dto_entry, tuple) and len(dto_entry) >= 2:
                                try:
                                    dto_json = json.loads(dto_entry[1])
                                    target_key = 'data'
                                    attribute_utils.add_attributes_to_payload(row, dto_json, env_config, target_key=target_key)
                                    
                                    # Re-package the DTO
                                    new_dto_content = json.dumps(dto_json)
                                    new_list = list(dto_entry)
                                    new_list[1] = new_dto_content
                                    kwargs['files']['dto'] = tuple(new_list)
                                    if getattr(builtins, 'DEBUG_MODE', False):
                                         print(f"   ✨ Injected Attributes into DTO.", flush=True)
                                except: pass

                # 3. Log FINAL Payload (Post-Injection) to verify changes
                if getattr(builtins, 'DEBUG_MODE', False) or auto_inject:
                    if kwargs.get('json'):
                         print(f"   📦 Final Payload: {json.dumps(kwargs['json'])}", flush=True)
                    elif 'files' in kwargs and 'dto' in kwargs['files']:
                         print(f"   📦 Final DTO: {kwargs['files']['dto'][1]}", flush=True)

                # 4. Execute original
                response = original_request(self, method, url, *args, **kwargs)
                
                # 4. Debug response logging
                if getattr(builtins, 'DEBUG_MODE', False):
                    print(f"📥 [INTERCEPTOR] Response: {response.status_code}", flush=True)
                    if response.status_code >= 400:
                        try:
                            preview = response.text[:200] if response.text else ""
                            print(f"   ⚠️ Error: {preview}", flush=True)
                        except: pass
                        
                return response

            requests.Session.request = intercepted_request
            print(f"✅ API Interceptor Active.", flush=True)
        else:
            print(f"⚠️  API Interceptor skipped (attribute_utils not available).", flush=True)
            
    except Exception as e:
        print(f"❌ Failed to setup API interceptor: {e}", flush=True)
        import traceback
        print(f"   Traceback: {traceback.format_exc()}", flush=True)
        print(f"⚠️  Continuing without API interceptor...", flush=True)

    print("🚀 Starting script execution...", flush=True)
    run_script(args.script, data, args.token, env_config)

