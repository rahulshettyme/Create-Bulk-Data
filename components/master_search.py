"""
Master Search Component
Centralized master data lookup to eliminate redundant API calls and reduce log verbosity.

Supports two modes:
1. "once" - Fetch all data once, lookup from cache (for small datasets like soil types)
2. "search" - Query API per row with caching (for large datasets like users, farmers)
"""

import requests
import json


def _get_nested_value(data, path):
    """
    Extract value from nested JSON using dot notation or array indices.
    
    Examples:
        path='id' -> data['id']
        path='data.id' -> data['data']['id']
        path='response[0].id' -> data['response'][0]['id']
        path='root.items[0].value' -> data['root']['items'][0]['value']
    
    Args:
        data: Dictionary or list to extract from
        path: Dot-separated path with optional array indices
    
    Returns:
        Extracted value or None if path doesn't exist
    """
    if not path or not data:
        return None
    
    try:
        # Handle simple key
        if '.' not in path and '[' not in path:
            return data.get(path) if isinstance(data, dict) else None
        
        # Parse complex path
        current = data
        parts = path.replace('[', '.').replace(']', '').split('.')
        
        for part in parts:
            if not part:
                continue
            
            # Handle array index
            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            # Handle dictionary key
            elif isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            else:
                return None
        
        return current
    except Exception:
        return None


def _resolve_path_variables(endpoint, path_variables_config, env_config, cache=None):
    """
    Resolve dynamic path variables in endpoint by calling setup APIs.
    
    Example:
        endpoint = "/users/search/companies/{company_id}"
        path_variables_config = {
            "company_id": {
                "setup_api": "/users/user-info",
                "extract_path": "companyId",
                "cache_key": "user_company_id"
            }
        }
        
        Returns: "/users/search/companies/1251"
    
    Args:
        endpoint: API endpoint with placeholders like {company_id}
        path_variables_config: Dict mapping placeholder names to their config
        env_config: Environment configuration
        cache: Optional cache to store resolved values
    
    Returns:
        Resolved endpoint string with placeholders replaced
    """
    if not path_variables_config:
        return endpoint
    
    resolved_endpoint = endpoint
    base_url = env_config.get('apiBaseUrl', '')
    token = env_config.get('token', '')
    
    # Ensure Bearer prefix
    if token and not token.startswith('Bearer '):
        token = f"Bearer {token}"
        
    headers = {'Authorization': token}
    
    for var_name, var_config in path_variables_config.items():
        placeholder = f"{{{var_name}}}"
        
        if placeholder not in resolved_endpoint:
            continue
        
        # Check cache first
        cache_key = var_config.get('cache_key', var_name)
        if cache is not None and cache_key in cache:
            resolved_endpoint = resolved_endpoint.replace(placeholder, str(cache[cache_key]))
            continue
        
        # Call setup API to get the value
        setup_api = var_config.get('setup_api')
        extract_path = var_config.get('extract_path')
        
        if not setup_api or not extract_path:
            raise ValueError(f"Missing setup_api or extract_path for variable '{var_name}'")
        
        try:
            setup_url = f"{base_url}{setup_api}"
            print(f"🔍 [MASTER_SEARCH] Resolving {{{var_name}}} via {setup_url}...", flush=True)
            
            response = requests.get(setup_url, headers=headers, timeout=30)
            
            if response.status_code == 401:
                raise PermissionError(f"401 Unauthorized for url: {setup_url}. Check token validity.")
            
            response.raise_for_status()
            
            data = response.json()
            value = _get_nested_value(data, extract_path)
            
            if value is None:
                raise ValueError(f"Could not extract '{extract_path}' from setup API response: {json.dumps(data)[:200]}...")
            
            # Cache the value
            if cache is not None:
                cache[cache_key] = value
            
            # Replace placeholder
            resolved_endpoint = resolved_endpoint.replace(placeholder, str(value))
            print(f"✅ [MASTER_SEARCH] Resolved {{{var_name}}} -> {value}", flush=True)
            
        except Exception as e:
            # CRITICAL: Re-raise to stop execution
            print(f"❌ [MASTER_SEARCH] Failed to resolve path variable '{var_name}': {e}", flush=True)
            raise e
    
    return resolved_endpoint


def fetch_all(master_type, env_config):
    """
    Fetch all master data at once (for "once" mode).
    
    Args:
        master_type: Type of master data (e.g., 'soiltype', 'irrigationtype')
        env_config: Environment configuration containing apiBaseUrl, token, master_data_config
    
    Returns:
        List of master data items or empty list on failure
    """
    master_config = env_config.get('master_data_config', {}).get(master_type)
    
    if not master_config:
        print(f"❌ [MASTER_SEARCH] Config not found for master type: {master_type}")
        return []
    
    base_url = env_config.get('apiBaseUrl', '')
    endpoint = master_config.get('api_endpoint', '')
    
    # Resolve path variables if any (e.g., {company_id})
    path_variables = master_config.get('path_variables')
    try:
        if path_variables:
            endpoint = _resolve_path_variables(endpoint, path_variables, env_config)
    except Exception as e:
        print(f"🛑 [MASTER_SEARCH] Aborting fetch_all for '{master_type}' due to resolution failure: {e}", flush=True)
        return []
    
    url = f"{base_url}{endpoint}"
    
    try:
        token = env_config.get('token', '')
        if token and not token.startswith('Bearer '):
            token = f"Bearer {token}"
            
        headers = {'Authorization': token}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle both list and dict responses
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common patterns: data.data, data.items, data.results
            items = data.get('data') or data.get('items') or data.get('results') or []
        else:
            items = []
        
        print(f"✅ [MASTER_SEARCH] Fetched {len(items)} items for '{master_type}'", flush=True)
        return items
    
    except Exception as e:
        print(f"❌ [MASTER_SEARCH] Failed to fetch '{master_type}': {e}", flush=True)
        return []


def search(master_type, query_value, env_config, cache=None):
    """
    Search for a specific master data item (for "search" mode).
    
    Args:
        master_type: Type of master data (e.g., 'user', 'farmer', 'project')
        query_value: Value to search for (e.g., user name from Excel)
        env_config: Environment configuration
        cache: Optional cache dictionary to avoid duplicate queries
    
    Returns:
        {
            'found': True/False,
            'value': <extracted value> or None,
            'message': Success/error message,
            'full_data': <complete API response item> (optional)
        }
    """
    if not query_value:
        return {
            'found': False,
            'value': None,
            'message': 'No query value provided'
        }
    
    master_config = env_config.get('master_data_config', {}).get(master_type)
    
    if not master_config:
        return {
            'found': False,
            'value': None,
            'message': f"Config not found for master type: {master_type}"
        }
    
    cache_key = f"{master_type}:{str(query_value).strip().lower()}"
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        if cached['found']:
            print(f"⚡ [MASTER_SEARCH] Cache hit: {master_type} '{query_value}' -> {cached['value']}", flush=True)
        return cached
    
    # Query API - All search APIs use 'query' parameter
    base_url = env_config.get('apiBaseUrl', '')
    endpoint = master_config.get('api_endpoint', '')
    
    # Resolve path variables if any (e.g., {company_id})
    # Pass cache to avoid re-fetching setup API data
    # Resolve path variables if any (e.g., {company_id})
    # Pass cache to avoid re-fetching setup API data
    path_variables = master_config.get('path_variables')
    try:
        if path_variables:
            endpoint = _resolve_path_variables(endpoint, path_variables, env_config, cache)
    except Exception as e:
         result = {
            'found': False,
            'value': None,
            'message': f"Path Resolution Failed: {str(e)}"
        }
         print(f"🛑 [MASTER_SEARCH] Aborting search for '{master_type}' due to resolution failure.", flush=True)
         return result

    url = f"{base_url}{endpoint}"
    
    try:
        token = env_config.get('token', '')
        if token and not token.startswith('Bearer '):
            token = f"Bearer {token}"
            
        headers = {'Authorization': token}
        
        # Custom Query Param Handling to enforce %20 instead of +
        # requests.get(params=...) produces + for spaces, which some APIs reject
        import urllib.parse
        encoded_query = urllib.parse.quote(str(query_value))
        
        # Check if URL already has params
        separator = '&' if '?' in url else '?'
        final_url = f"{url}{separator}query={encoded_query}"
        
        response = requests.get(final_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle both list and dict responses
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('data') or data.get('items') or data.get('results') or []
        else:
            items = []
        
        # Match against the specified field in response
        match_field = master_config.get('match_field', 'name')
        normalized_query = str(query_value).strip().lower()
        
        matched_item = None
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # Get the field value to compare
            item_value = _get_nested_value(item, match_field)
            if item_value and str(item_value).strip().lower() == normalized_query:
                matched_item = item
                break
        
        if not matched_item:
            result = {
                'found': False,
                'value': None,
                'message': master_config.get('not_found_message', f"{master_config.get('name', master_type)} not found")
            }
            print(f"ℹ️ [MASTER_SEARCH] Search: {master_type} - '{query_value}' | Result: Not Found (Field: '{match_field}')", flush=True)
        else:
            # Extract value using lookup_path
            lookup_path = master_config.get('lookup_path', 'id')
            extracted_value = _get_nested_value(matched_item, lookup_path)
            
            result = {
                'found': True,
                'value': extracted_value,
                'message': 'Success',
                'full_data': matched_item
            }
            print(f"✅ [MASTER_SEARCH] Search: {master_type} - '{query_value}' | Result: Found | Value: {extracted_value}", flush=True)
        
        # Cache result
        if cache is not None:
            cache[cache_key] = result
        
        return result
    
    except Exception as e:
        result = {
            'found': False,
            'value': None,
            'message': f"API error: {str(e)}"
        }
        print(f"[MASTER_SEARCH] Search: {master_type} - '{query_value}' | Result: Error | Details: {e}", flush=True)
        
        # Cache failures too to avoid retrying
        if cache is not None:
            cache[cache_key] = result
        
        return result


def lookup_from_cache(cache_data, match_field, lookup_value, return_path='id'):
    """
    Lookup a value from cached master data (for "once" mode).
    
    Args:
        cache_data: List of master data items (from fetch_all)
        match_field: Field to match against (e.g., 'name', 'code', 'data.email')
        lookup_value: Value to search for
        return_path: Path to extract from matched item (e.g., 'id', 'data.code')
    
    Returns:
        {
            'found': True/False,
            'value': <extracted value> or None,
            'message': Success/error message,
            'full_data': <matched item> (optional)
        }
    """
    if not lookup_value or not cache_data:
        return {
            'found': False,
            'value': None,
            'message': 'No lookup value or empty cache'
        }
    
    # Normalize lookup value
    normalized_lookup = str(lookup_value).strip().lower()
    
    # Search cache
    for item in cache_data:
        if not isinstance(item, dict):
            continue
        
        item_value = _get_nested_value(item, match_field)
        if item_value and str(item_value).strip().lower() == normalized_lookup:
            # Found match
            extracted_value = _get_nested_value(item, return_path)
            print(f"✅ [MASTER_SEARCH] Search: {match_field} - '{lookup_value}' -> Found: {extracted_value}", flush=True)
            return {
                'found': True,
                'value': extracted_value,
                'message': 'Success',
                'full_data': item
            }
    
    # Not found
    print(f"ℹ️ [MASTER_SEARCH] Search: {match_field} - '{lookup_value}' -> Not Found", flush=True)
    return {
        'found': False,
        'value': None,
        'message': f"Value '{lookup_value}' not found in cache"
    }
