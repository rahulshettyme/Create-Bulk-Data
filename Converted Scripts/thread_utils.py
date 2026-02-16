import concurrent.futures
import builtins

def run_in_parallel(process_func, items, max_workers=10, token=None, env_config=None):
    """
    Runs process_func on each item in items list in parallel.
    Maintains the order of results corresponding to items.
    
    Args:
        process_func (callable): Function that takes a single item and returns the result.
        items (list): List of items to process.
        max_workers (int): Number of parallel threads.
        token (str, optional): Bearer token to inject into builtins for process_func.
        env_config (dict, optional): Environment configuration to inject into builtins for process_func.
        
    Returns:
        list: List of results in the same order as input items.
    """
    # Inject token and env_config into builtins so they're accessible in process_func
    # This is needed because ThreadPoolExecutor doesn't easily pass extra context
    if token is not None:
        builtins.token = token
    if env_config is not None:
        builtins.env_config = env_config
        # DEBUG: Check if token is present in env_config
        token_status = "PRESENT" if 'token' in env_config else "MISSING"
        print(f"DEBUG: thread_utils injected env_config. Token: {token_status}", flush=True)
    
    results = [None] * len(items)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Map futures to their original index to preserve order
        def wrapped_process(index, item):
            try:
                # Set thread-local context for attribute injection
                from components import attribute_utils
                attribute_utils.set_current_row(item)
            except: pass
            return process_func(item)

        future_to_index = {
            executor.submit(wrapped_process, i, item): i 
            for i, item in enumerate(items)
        }
        
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                # Fallback error handling if process_func crashes completely
                # Try to return something meaningful based on input type
                original = items[index]
                if isinstance(original, dict):
                    err_res = original.copy()
                else:
                    err_res = {"input": str(original)}
                    
                err_res['Status'] = 'Fail'
                err_res['API_Response'] = f"Thread Execution Error: {str(e)}"
                results[index] = err_res
                
    return results

def create_lock():
    """
    Creates and returns a new threading.Lock object.
    Useful for ensuring thread-safe operations in AI generated scripts.
    """
    import threading
    return threading.Lock()
