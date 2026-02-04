import concurrent.futures

def run_in_parallel(process_func, items, max_workers=10):
    """
    Runs process_func on each item in items list in parallel.
    Maintains the order of results corresponding to items.
    
    Args:
        process_func (callable): Function that takes a single item and returns the result.
        items (list): List of items to process.
        max_workers (int): Number of parallel threads.
        
    Returns:
        list: List of results in the same order as input items.
    """
    results = [None] * len(items)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Map futures to their original index to preserve order
        future_to_index = {
            executor.submit(process_func, item): i 
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
