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
    try:
        # 1. Parse Inputs
        # data is already a list/dict passed from main
        env_config = json.loads(env_config_json)
        
        
        # Inject Google API Key for Geofencing (FORCE OVERWRITE to ensure correct key is used)
        # 1. Try Environment Variables (Prioritize Specific Key)
        key = os.environ.get("GEOCODING_API_KEY", "").strip() or \
              os.environ.get("GOOGLE_API_KEY", "").strip()

        if not key:
            try:
                # 2. Try secrets.json / db.json (Local Development)
                # runner_bridge is in Manager/
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
                for filename in ["System/secrets.json", "System/db.json"]:
                    path = os.path.join(base_dir, filename)
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            # Start with specific key overrides if they exist, else fallback to generic gemini key
                            data_json = json.load(f)
                            # PRIORITY: Use Geocoding_api_key for Runner/Scripts if available
                            key = data_json.get("Geocoding_api_key", "").strip() or \
                                  data_json.get("google_api_key", "").strip() or \
                                  data_json.get("gemini_api_key", "").strip()
                            if key: break
            except: pass
        
        # Only overwrite if we actually found a key, otherwise leave what might vary be there
        if key:
            env_config['google_api_key'] = key
        
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
                    
                    # NO REORDERING - Return exact output from script
                    # This allows new columns (e.g. results) to appear naturally.
                    # if hasattr(builtins, 'output_columns') and builtins.output_columns: ... (Removed)


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
    output_columns = json.loads(args.columns) if args.columns else []

    # Inject builtins
    builtins.data = data
    builtins.token = args.token
    builtins.env_config = env_config
    builtins.output_columns = output_columns
    
    run_script(args.script, data, args.token, args.env)
