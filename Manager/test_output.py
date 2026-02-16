# AI Generated - 2026-02-16 22:52:17 IST
# CONFIG: enableGeofencing = False
# CONFIG: allowAdditionalAttributes = False
# EXPECTED_INPUT_COLUMNS: Asset Name, Farmer Name, Farmer Name_id, Status, Response
import requests
import json
import thread_utils  # Direct import, NOT 'from components import thread_utils'
import builtins  # Required for accessing token/env_config
import components.master_search as master_search  # NOT 'from components import master_search'

# --- CRITICAL Module-level variables for Master Search caching and thread safety ---
_farmer_cache = {}
# Initialize a lock for thread-safe access to _farmer_cache
_lock = thread_utils.create_lock()

# This flag will be set in the run() function based on input data,
# determining if 'Farmer Name_id' should be used directly.
_use_provided_farmer_ids = False


def run(data, token, env_config):
    """
    Main function to orchestrate the asset creation process in parallel.

    Args:
        data (list[dict]): A list of dictionaries, where each dictionary represents a row
                           from the input data.
        token (str): The authorization token for API calls.
        env_config (dict): A dictionary containing environment-specific configurations
                           (e.g., API base URLs).
    Returns:
        list[dict]: The processed data with 'Status' and 'Response' columns updated.
    """
    # CRITICAL: Set the _use_provided_farmer_ids flag at the start of run()
    # This checks if the 'Farmer Name_id' column exists in the first row of data
    # and has a non-empty value, indicating that provided IDs should be used.
    global _use_provided_farmer_ids
    _use_provided_farmer_ids = bool(data and data[0].get('Farmer Name_id'))

    # CRITICAL: thread_utils.run_in_parallel injects token and env_config into builtins.
    # process_row will access them via builtins.token and builtins.env_config.
    return thread_utils.run_in_parallel(process_func=process_row, items=data, token=token, env_config=env_config)


def process_row(row):
    """
    Processes a single row of data to search for a farmer and create an asset.
    This function is designed to be run in parallel.

    Args:
        row (dict): A dictionary representing a single row of input data.

    Returns:
        dict: The updated row dictionary with 'Status' and 'Response' columns.
              CRITICAL: The original row dict is modified and returned to preserve
                        all input columns.
    """
    row['Status'] = 'Fail'  # Default status for the row
    row['Response'] = ''    # Default empty response message

    # Extract required input columns
    farmer_name = row.get('Farmer Name')
    asset_name = row.get('Asset Name')
    farmer_id = None

    # --- Input Validation ---
    if not farmer_name:
        row['Response'] = 'Input Error: Farmer Name is missing.'
        return row
    if not asset_name:
        row['Response'] = 'Input Error: Asset Name is missing.'
        return row

    # --- Step 1: Master Search for Farmer ---
    if _use_provided_farmer_ids:
        # CRITICAL: STRICT MODE - Use provided ID from 'Farmer Name_id' column.
        farmer_id = row.get('Farmer Name_id')
        if not farmer_id:
            row['Response'] = 'Farmer Name_id is empty (Strict Mode). Cannot create asset without a valid Farmer ID.'
            # CRITICAL: Logging requirement for lookup type
            print(f"[FARMER_LOOKUP] {farmer_name} → ID: Not Found (Empty in Strict Mode)")
            return row
        # CRITICAL: Logging requirement for lookup type
        print(f"[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id} (Provided)")
    else:
        # CRITICAL: FALLBACK MODE - Perform Master Search if ID not provided or flag is false.
        # CRITICAL: Use thread-safe lock for cache access
        with _lock:
            farmer_search_result = master_search.search('farmer', farmer_name, builtins.env_config, _farmer_cache)
        
        if not farmer_search_result['found']:
            row['Response'] = farmer_search_result['message']
            # CRITICAL: Logging requirement for lookup type
            print(f"[FARMER_LOOKUP] {farmer_name} → Result: Not Found. Message: {farmer_search_result['message']}")
            return row
        
        farmer_id = farmer_search_result['value']
        # CRITICAL: Logging requirement for lookup type
        print(f"[FARMER_LOOKUP] {farmer_name} → ID: {farmer_id}")

    # --- Step 2: Create Asset with Farmer ID ---
    base_url = builtins.env_config.get('apiBaseUrl')
    if not base_url:
        row['Response'] = 'Configuration Error: API base URL not found in environment configuration.'
        return row

    # CRITICAL: Construct the API URL using f-string to avoid urljoin issues.
    # The prompt describes 'create asset with farmer ID', but doesn't provide
    # the exact API endpoint. A common pattern is /resource-service/api/resources or similar.
    # Assuming 'asset-service/api/assets' as a plausible endpoint.
    create_asset_url = f'{base_url}/asset-service/api/assets' 

    payload = {
        'name': asset_name,
        'farmerId': farmer_id,
        # Add any other static or derived fields for asset creation as per API contract
        # Example: 'status': row.get('Status', 'Active') # If 'Status' input column is for asset status
    }

    # CRITICAL: Check if API expects Multipart/DTO. Description does not imply it for this step.
    # Assuming standard JSON payload.
    headers = {
        'Authorization': f'Bearer {builtins.token}',
        'Content-Type': 'application/json' 
    }

    try:
        response = requests.post(create_asset_url, headers=headers, json=payload)

        # CRITICAL: Check for success using response.ok (covers 200, 201, etc.)
        if response.ok:
            response_json = response.json()
            # Extract relevant info from response, e.g., the ID of the newly created asset
            created_asset_id = response_json.get('id', 'N/A')
            row['Status'] = 'Success'
            row['Response'] = f'Asset created successfully. Asset ID: {created_asset_id}'
        else:
            row['Response'] = (f'API Error: Failed to create asset. Status: {response.status_code}, '
                                f'Error: {response.text}')

    except requests.exceptions.RequestException as e:
        row['Response'] = f'Network or API connection error during asset creation: {e}'
    except json.JSONDecodeError:
        # This occurs if response.json() fails, often for non-2xx responses or empty bodies
        row['Response'] = f'API Error: Failed to decode JSON response from asset creation API. ' \
                           f'Status: {response.status_code}, Response: {response.text}'
    except Exception as e:
        row['Response'] = f'An unexpected error occurred during asset creation: {e}'

    return row
