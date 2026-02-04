
# Test Script for Bulk Data Manager

SCRIPT_METADATA = {
    "name": "Test Python Script",
    "description": "Verifies the Python Runner integration.",
    "team": "QA", 
    "expected_columns": [
        "Farmer Code",
        "Test Value"
    ]
}

def run(data, token, env_config):
    results = []
    print(f"DEBUG: Received {len(data)} rows. Token length: {len(token)}")
    
    for row in data:
        row["Status"] = "Pass"
        row["API_Response"] = f"Processed: {row.get('Test Value', 'N/A')}"
        results.append(row)
        
    return results
