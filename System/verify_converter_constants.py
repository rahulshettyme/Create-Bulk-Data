import sys
import os
import ast

# Add the Manager directory to sys.path
sys.path.append(r'c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Manager')

from script_converter import convert_code

# Mock input code that mimics the failure case
mock_code = """
import requests

base_url = "http://mock.com"
SHEET_NAME = "Plot_details"
DELETE_API = f"{base_url}/delete"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 30 + 5

def process(name=SHEET_NAME, api=DELETE_API, headers=HEADERS):
    print(f"Processing {name} at {api}")

def main():
    process()

if __name__ == "__main__":
    main()
"""

print("--- INPUT CODE ---")
print(mock_code)

try:
    print("\n--- CONVERTING ---")
    converted_code = convert_code(mock_code)
    
    print("\n--- CONVERTED CODE ---")
    print(converted_code)
    
    print("\n--- VERIFYING AST ---")
    tree = ast.parse(converted_code)
    run_func = tree.body[0]
    
    # We expect order:
    # 1. Imports
    # 2. Setup/Wrappers
    # 3. Constant (SHEET_NAME = ...)
    # 4. Func Definition (def process(name=SHEET_NAME))
    # 5. Main Guard
    
    assign_found_at = -1
    def_found_at = -1
    
    for i, node in enumerate(run_func.body):
        # Check for SHEET_NAME assignment
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'SHEET_NAME':
                    assign_found_at = i
                    print(f"FOUND: Assignment at index {i}")
                    
        # Check for process definition
        if isinstance(node, ast.FunctionDef) and node.name == 'process':
            def_found_at = i
            print(f"FOUND: Function def at index {i}")

    if assign_found_at != -1 and def_found_at != -1:
        if assign_found_at < def_found_at:
             print("PASS: Assignment is BEFORE Function Definition")
        else:
             print("FAIL: Assignment is AFTER Function Definition")
             sys.exit(1)
    else:
        print("FAIL: Nodes not found")
        sys.exit(1)

except Exception as e:
    print(f"FAIL: Conversion or Verification failed: {e}")
    sys.exit(1)
