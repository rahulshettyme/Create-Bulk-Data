
import sys
import json
import logging
from unittest.mock import MagicMock
import types
import builtins
import pandas as pd
import io

# Force UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Setup Environment
sys.path.append(r"c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Manager")
import script_converter

# 2. Mock Logic WITH Run Function
source_code = """
import pandas as pd
import builtins

def run(data, token, env_config):
    # Simulate what PR_Disable does
    df = builtins.data_df
    # Add a new column
    df['Status'] = 'Success'
    
    # Return stale data (original list)
    return data
"""

# 3. Convert
print("Converting code...")
converted_code = script_converter.convert_code(source_code, no_threading=True)

# 4. Execute
print("Executing converted code...")
global_context = {
    'data': [
        {"id": 1, "name": "A"},
        {"id": 2, "name": "B"}
    ],
    'token': "TOKEN",
    'env_config': {}
}

try:
    exec(converted_code, global_context)
    run_func = global_context['run']
    
    # Passing global_context['data'] which is the list
    results = run_func(global_context['data'], "TOKEN", {})
    
    print("\n--- RESULTS ---")
    print(json.dumps(results, indent=2))
    
    # Verification
    if results[0].get('Status') == 'Success':
        print("\n✅ PASSED: Data was synced from DataFrame (Override successful).")
    else:
        print("\n❌ FAILED: Data was NOT synced (Stale data returned).")
        
except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
