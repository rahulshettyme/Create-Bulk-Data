import ast
import json
import sys
import re
import os

# Add current directory to path to allow importing sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from script_reverser import reverse_engineer_script
except ImportError:
    # Fallback if running from a different context where relative import might fail
    try:
        from Manager.script_reverser import reverse_engineer_script
    except:
        pass # Handle checking later

def analyze_script(code_content):
    """
    Analyzes Python code to extract input columns and End-to-End workflow steps.
    Uses AI (Gemini) via script_reverser for logic extraction.
    """
    input_columns = []
    
    # 0. Check for Explicit Input Columns Comment (Source of Truth)
    try:
        lines = code_content.splitlines()
        for line in lines[:20]: # Check first 20 lines
            if line.strip().startswith("# EXPECTED_INPUT_COLUMNS:") or line.strip().startswith("# Excel Columns"):
                col_str = line.split(":", 1)[1].strip()
                if col_str:
                     # Split and clean, keeping order
                     input_columns = [c.strip() for c in col_str.split(',') if c.strip()]
                break
    except:
        pass

    # 0b. Check for Explicit UI Output Definition (Source of Truth)
    ui_columns = []
    try:
        # Regex to find: # - UI Column 'ID' (handling various indentation/spacing)
        explicit_ui = re.findall(r"#\s*-\s*UI Column '([^']+)'", code_content)
        if explicit_ui:
            ui_columns = explicit_ui
    except:
        pass

    # 1. AI Analysis
    try:
        if 'reverse_engineer_script' not in globals():
             return {"error": "Module script_reverser not found. Please ensure it exists in Manager/ directory."}

        # Call the Reverser
        ai_result = reverse_engineer_script(code_content)
        
        if "error" in ai_result:
            return {"error": ai_result["error"]}

        # 2. Merge Columns (Explicit wins, then AI)
        if not input_columns:
            input_columns = ai_result.get("excelColumns", [])
            
        if not ui_columns:
            ui_columns = ai_result.get("uiColumns", [])

        # 3. Format Steps for Frontend (HTML)
        steps = ai_result.get("steps", [])
        final_steps_html = []
        
        for idx, step in enumerate(steps):
            step_type = step.get("type", "LOGIC")
            name = step.get("apiName", f"Step {idx+1}")
            
            # Badge
            color = "#38bdf8" if step_type == "API" else "#eab308" # Blue for API, Yellow for Logic
            badge = f"<span style='background:{color}aa; padding:2px 6px; border-radius:4px; font-size:0.7em; margin-right:8px; color:white; border:1px solid {color};'>{step_type}</span>"
            
            header = f"<div>{badge}<strong>{name}</strong></div>"
            
            details = []
            
            if step_type == "API":
                method = step.get("method", "")
                endpoint = step.get("endpoint", "")
                if method or endpoint:
                    details.append(f"<li><strong>Call:</strong> {method} <code>{endpoint}</code></li>")
                
                payload = step.get("payload")
                if payload and payload != "None":
                    # Truncate if too long?
                    if len(payload) > 150:
                        payload = payload[:147] + "..."
                    details.append(f"<li><strong>Payload:</strong> {payload}</li>")
                    
                resp = step.get("response")
                if resp:
                    details.append(f"<li><strong>Response:</strong> {resp}</li>")
                    
            logic = step.get("instruction") or step.get("logic")
            if logic:
                details.append(f"<li style='color:#cbd5e1;'>{logic}</li>")
                
            ul_html = ""
            if details:
                ul_html = f"<ul style='margin-top:5px; margin-bottom:10px; font-size:0.85em; color:var(--text-secondary); padding-left:20px; list-style-type: disc;'>{''.join(details)}</ul>"
            
            final_steps_html.append(header + ul_html)

        if not final_steps_html:
            final_steps_html = ["<div style='color:gray;'>No steps detected by AI analysis.</div>"]

        return {
            "inputColumns": input_columns,
            "uiColumns": ui_columns,
            "workflowDescription": final_steps_html,
            "raw_ai": ai_result # debug
        }

    except Exception as e:
        return {"error": f"AI Analysis Exception: {str(e)}"}    

if __name__ == "__main__":
    try:
        # Check stdin encoding for windows
        if sys.platform == 'win32':
             sys.stdin.reconfigure(encoding='utf-8')

        code = sys.stdin.read()
        if not code:
            print(json.dumps({"error": "No code provided"}))
            sys.exit(1)
            
        analysis = analyze_script(code)
        
        # Check if analysis itself returned an error dict
        if "error" in analysis and len(analysis) == 1:
             output = { "status": "error", "message": analysis["error"] }
        else:
             output = { "status": "success", "data": analysis }
             
    except Exception as e:
        output = { "status": "error", "message": str(e) }
        
    print("---JSON_START---")
    print(json.dumps(output))
