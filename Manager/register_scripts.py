
import os
import json
import importlib.util
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DIR = os.path.join(BASE_DIR, "Original Scripts")
CONVERTED_DIR = os.path.join(BASE_DIR, "Converted Scripts")

def register_scripts():
    print(f"Scanning for scripts in: {ORIGINAL_DIR}")
    
    if not os.path.exists(ORIGINAL_DIR):
        print(f"Original Scripts directory not found at {ORIGINAL_DIR}")
        print("Note: 'Original Scripts' functionality is deprecated. Focusing on Converted/Draft scripts.")
        return

    if not os.path.exists(CONVERTED_DIR):
        os.makedirs(CONVERTED_DIR)

    scripts_found = 0
    
    for filename in os.listdir(ORIGINAL_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = os.path.join(ORIGINAL_DIR, filename)
            
            try:
                # Load the module dynamically
                spec = importlib.util.spec_from_file_location("user_script", filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Extract Metadata
                if hasattr(module, "SCRIPT_METADATA"):
                    metadata = module.SCRIPT_METADATA
                    metadata["filename"] = filename # Add filename for the runner
                    
                    # Generate Config JSON
                    config_filename = filename.replace(".py", ".json")
                    config_path = os.path.join(CONVERTED_DIR, config_filename)
                    
                    with open(config_path, "w") as f:
                        json.dump(metadata, f, indent=4)
                        
                    print(f"[SUCCESS] Registered: {filename} -> {config_filename}")
                    scripts_found += 1
                else:
                    print(f"[SKIP] {filename}: Missing SCRIPT_METADATA variable.")
                    
            except Exception as e:
                print(f"[ERROR] Failed to load {filename}: {str(e)}")

    print(f"\nDone! Registered {scripts_found} scripts.")
    print("Restart your dashboard server if needed, or refresh the page.")

if __name__ == "__main__":
    register_scripts()
