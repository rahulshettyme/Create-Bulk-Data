
import sys
import os

# Setup path to import Manager modules
sys.path.append(r"c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Manager")
import script_converter

draft_path = r"c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Draft Scripts\PR_Disable.py"
converted_path = r"c:\Users\cropin\Documents\Important\AntiGravity\Data Generate\Converted Scripts\PR_Disable.py"

print(f"Reading draft from {draft_path}...")
with open(draft_path, 'r', encoding='utf-8') as f:
    source_code = f.read()

print("Converting code...")
# no_threading=True because the script handles threading itself or is intended to be sequential
converted_code = script_converter.convert_code(source_code, no_threading=True)

print(f"Writing converted code to {converted_path}...")
with open(converted_path, 'w', encoding='utf-8') as f:
    f.write(converted_code)

print("✅ Regeneration Complete.")
