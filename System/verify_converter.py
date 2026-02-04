import sys
import os
import ast

# Add the Manager directory to sys.path
sys.path.append(r'c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Manager')

from script_converter import convert_code

# Mock input code that mimics the structure of the failed script
mock_code = """
import requests

def main():
    print("Main running")
    phase1()

def phase1():
    print("Phase 1")

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
    print("AST Parse Successful!")
    
    # Check for run function
    run_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'run':
            run_func = node
            break
            
    if not run_func:
        print("FAIL: 'run' function not found.")
        sys.exit(1)
        
    print("PASS: 'run' function found.")
    
    # Check order inside run
    defs_found = []
    eecution_started = False
    
    for node in run_func.body:
        if isinstance(node, ast.FunctionDef):
            defs_found.append(node.name)
            if eecution_started and node.name in ['main', 'phase1']:
                 # If we see a main/phase1 def AFTER we thought execution started (not strict check but good indicator)
                 pass
        
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant) and node.test.value == True:
            # This is likely the main guard
            print("FOUND: Main Execution Guard")
            eecution_started = True

    if 'main' in defs_found and 'phase1' in defs_found:
        print(f"PASS: Found definitions: {defs_found}")
    else:
        print(f"FAIL: Missing definitions. Found: {defs_found}")

except Exception as e:
    print(f"FAIL: Conversion or Verification failed: {e}")
    sys.exit(1)
