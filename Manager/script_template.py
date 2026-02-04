
# Script Template for Bulk Data Manager
# Place this file in: Data generate/Original Scripts/
# Run 'register_scripts.py' to add it to the Dashboard.

# Metadata used by the Dashboard
SCRIPT_METADATA = {
    "name": "My Custom Script",
    "description": "Description of what this script does.",
    "team": "QA",  # Options: "QA", "CS", "Both"
    "expected_columns": [
        "Farmer Code",
        "Asset Name",
        "Address",
        "Some Value"
    ]
}

def run(data, token, env_config):
    """
    Main execution function called by the Dashboard.
    
    Args:
        data (list of dict): Rows from the uploaded Excel file.
        token (str): Bearer token for the current user/session.
        env_config (dict): Contains 'apiBaseUrl' and 'filesUrl'.
        
    Returns:
        list of dict: The processed data to be displayed/downloaded.
    """
    import requests
    # Import shared threading utility
    # Ensure thread_utils.py is in 'Converted Scripts' or python path
    try:
        import thread_utils
        USE_THREADING = True
    except ImportError:
        # Fallback if specific runner environment differs
        USE_THREADING = False
    
    # --- Config ---
    base_url = env_config.get('apiBaseUrl')
    if not base_url:
         raise ValueError("Missing 'apiBaseUrl' in env_config")
    headers = {"Authorization": f"Bearer {token}"}

    # --- Process Function ---
    def process_row(row):
        new_row = row.copy()
        try:
            # Example Logic
            farmer_code = new_row.get("Farmer Code")
            
            if not farmer_code:
                new_row["Status"] = "Failed"
                new_row["API_Response"] = "Missing Farmer Code"
            else:
                # Perform API Call
                # resp = requests.get(f"{base_url}/endpoint", headers=headers)
                
                # Mock Success
                new_row["Status"] = "Success"
                new_row["API_Response"] = "Processed successfully via Threading"
                
        except Exception as e:
            new_row["Status"] = "Failed"
            new_row["API_Response"] = str(e)
            
        return new_row

    # --- Execution ---
    if USE_THREADING:
        # Run in parallel (default 10 workers)
        return thread_utils.run_in_parallel(process_row, data)
    else:
        # Fallback sequential
        return [process_row(r) for r in data]
