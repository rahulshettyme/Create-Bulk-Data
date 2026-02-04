
import ast
import sys
import argparse
import os

class ScriptCleaner(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.ignore_modules = {'RS_access_token_generate', 'openpyxl', 'GetAuthtoken'}
        self.ignore_funcs = {'get_bearer_token', 'load_workbook', 'read_excel', 'get_access_token'}
        self.in_function_depth = 0
        self.removed_vars = set()
        self.in_loop = False
        self.worker_func_name = None
        self.current_func_name = None
        self.loop_body = None  # To capture the logic inside the main loop
        self.loop_target = None # 'row' variable name

    def visit_AsyncFunctionDef(self, node):
        self.in_function_depth += 1
        self.generic_visit(node)
        self.in_function_depth -= 1
        return node

    def visit_FunctionDef(self, node):
        self.in_function_depth += 1
        
        prev = self.current_func_name
        self.current_func_name = node.name

        # REPLACEMENT: get_cell_value(row, header) -> row.get(header)
        if node.name == 'get_cell_value':
            # We construct AST for this logic with TRACE LOGGING
            new_body_source = """
import builtins
import json
# Handle Integer Index (Excel Row Number)
if isinstance(row, int):
    idx = row - 2
    if hasattr(builtins, 'data') and isinstance(builtins.data, list) and 0 <= idx < len(builtins.data):
        row = builtins.data[idx]
    else:
        return ""

if not isinstance(row, dict): return ""
target = str(header).strip().lower()
found_val = ""
found_key = ""

for k, v in row.items():
    if str(k).strip().lower() == target: 
        found_val = v
        found_key = k
        break
    if str(k).strip().replace('_', ' ').lower() == target.replace('_', ' '): 
        found_val = v
        found_key = k
        break

# TRACE LOG
try:
    _trace_idx = row.get('_row_index', -1)
    print(f"[TRACE_DATA_READ] [Row {_trace_idx}] Key: {header} | Found: {found_key} | Value: {found_val}")
except: pass

return found_val
"""
            # Parse and replace body
            try:
                new_body = ast.parse(new_body_source).body
                node.body = new_body
                if len(node.args.args) >= 2:
                    node.args.args[0].arg = 'row'
                    node.args.args[1].arg = 'header'
            except Exception:
                pass
            
            self.generic_visit(node)
            self.current_func_name = prev
            return node

        # REPLACEMENT: set_cell_value
        if node.name == 'set_cell_value':
            new_body_source = """
if not isinstance(row, dict): return False
target = str(header).strip().lower()
match = None
for k in row.keys():
    if str(k).strip().lower() == target:
        match = k
        break
if match:
    row[match] = value
else:
    row[header] = value

# TRACE LOG
try:
    _trace_idx = row.get('_row_index', -1)
    print(f"[TRACE_DATA_WRITE] [Row {_trace_idx}] Key: {header} | Value: {value}")
except: pass

return True
"""
            try:
                new_body = ast.parse(new_body_source).body
                node.body = new_body
                if len(node.args.args) >= 3:
                    node.args.args[0].arg = 'row'
                    node.args.args[1].arg = 'header'
                    node.args.args[2].arg = 'value'
            except Exception:
                pass
            
            self.generic_visit(node)
            self.current_func_name = prev
            return node

        self.generic_visit(node)
        self.current_func_name = prev
        self.in_function_depth -= 1
        return node

    def visit_If(self, node):
        # SPECIAL HANDLING: Bypass `if not env_url:` check
        if (isinstance(node.test, ast.UnaryOp) and 
            isinstance(node.test.op, ast.Not) and 
            isinstance(node.test.operand, ast.Name) and 
            node.test.operand.id == 'env_url'):
            
            # Replace the entire body (which usually raises Error) with assignment from config
            # env_url = builtins.env_config.get('apiBaseUrl', '')
            override_source = "env_url = builtins.env_config.get('apiBaseUrl', '')"
            try:
                node.body = ast.parse(override_source).body
                # Also clear 'orelse' if any
                node.orelse = []
                return node
            except: pass

        self.generic_visit(node)
        if not node.body:
            node.body.append(ast.Pass())
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        if not node.body:
            node.body.append(ast.Pass())
        return node


    def visit_Import(self, node):
        new_names = [n for n in node.names if n.name not in self.ignore_modules or n.name == 'pandas']
        if not new_names:
            return None 
        node.names = new_names
        return node
    
    def visit_ImportFrom(self, node):
        if node.module in self.ignore_modules:
            return None
        return node


    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):
            name = self._get_func_name(node.value)
            if name == 'read_excel':
                 # FORCE SINGLE SHEET DATA
                 if self.current_func_name:
                     self.worker_func_name = self.current_func_name
                 node.value = ast.Attribute(
                     value=ast.Name(id='builtins', ctx=ast.Load()),
                     attr='data_df',
                     ctx=ast.Load()
                 )
                 # If original was `df_token = pd.read_excel(...)`, it now becomes `df_token = builtins.data_df`
                 # This effectively makes ANY excel read use the main data.
                 return node
            if name == 'load_workbook':
                 # Mock Workbook instantiation
                 node.value = ast.Call(
                     func=ast.Name(id='MockWorkbook', ctx=ast.Load()),
                     args=[ast.Name(id='builtins', ctx=ast.Load())], # Pass builtins (it has .data)
                     keywords=[]
                 )
                 return node
            
            if name in self.ignore_funcs:
                return None
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in ['base_url', 'env_key', 'file_path']:
                    return None
                # REMOVE TOKEN ASSIGNMENT -> Enforce Platform Token
                if target.id == 'token':
                    return None
                
                # Handling 'access_token = get_access_token()' or similar
                if target.id in ['access_token', 'bearer_token']:
                    node.value = ast.Name(id='token', ctx=ast.Load()) 
                    return node
        
        for target in node.targets:
             if isinstance(target, ast.Name) and target.id in ['env_url', 'environment_url']:
                 node.value = ast.Name(id='base_url', ctx=ast.Load())
                 return node

        if self._uses_removed_var(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in ['data_df', 'base_url', 'env_key', 'token', 'file_path', 'env_url', 'environment_url']:
                        continue
                    self.removed_vars.add(target.id)
            return None
        
        self.generic_visit(node) # REQUIRED for visit_Call to work on assigned values
        return node
        

    
    def visit_Attribute(self, node):
        # DETECT: row.iloc
        if node.attr == 'iloc' and isinstance(node.value, ast.Name):
             # We can't replace .iloc directly, it's usually part of a Subscript (row.iloc[0])
             # So we defer to visit_Subscript
             pass
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        # TRANSFORM: row.iloc[i] -> _safe_iloc(row, i)
        if isinstance(node.value, ast.Attribute) and node.value.attr == 'iloc':
             if isinstance(node.value.value, ast.Name): # target object (e.g. 'row')
                  target_name = node.value.value.id
                  
                  # Check if it is integer index
                  idx_node = node.slice
                  
                  # Construct safe call
                  new_node = ast.Call(
                      func=ast.Name(id='_safe_iloc', ctx=ast.Load()),
                      args=[
                          ast.Name(id=target_name, ctx=ast.Load()),
                          idx_node
                      ],
                      keywords=[]
                  )
                  return new_node
        return self.generic_visit(node)

    def visit_Call(self, node):
        # SKIP if inside the logger function itself (Prevent Recursion)
        if self.current_func_name == '_log_req':
            return self.generic_visit(node)

        # Improved Detection
        full_name = self._get_full_func_name(node)
        if full_name == 'requests.get':
            node.func = ast.Name(id='_log_get', ctx=ast.Load())
        elif full_name == 'requests.post':
            node.func = ast.Name(id='_log_post', ctx=ast.Load())
        elif full_name == 'requests.put':
            node.func = ast.Name(id='_log_put', ctx=ast.Load())
        elif full_name == 'requests.delete':
            node.func = ast.Name(id='_log_delete', ctx=ast.Load())
            
        self.generic_visit(node)
        return node

    def visit_For(self, node):
        # SKIP EXTRACTION IF INSIDE A FUNCTION
        if self.in_function_depth > 0:
            return self.generic_visit(node)

        # DETECT MAIN DATA LOOP
        is_excel_loop = False
        if isinstance(node.iter, ast.Call):
            name = self._get_func_name(node.iter)
            if name in ['read_excel', 'iter_rows', 'iterrows'] or name in self.ignore_funcs:
                 is_excel_loop = True
        
        # FIX: Detect 'for row in data'
        if isinstance(node.iter, ast.Name) and node.iter.id == 'data':
            is_excel_loop = True

        if not is_excel_loop and self._uses_removed_var(node.iter):
             is_excel_loop = True


        if is_excel_loop:
            # VISIT BODY FIRST (to apply _log_req replacements)
            # NodeTransformer.visit expects single node, returns node or list or None
            transformed_body = []
            for item in node.body:
                res = self.visit(item)
                if res is None: continue
                if isinstance(res, list): transformed_body.extend(res)
                else: transformed_body.append(res)
            
            # CAPTURE BODY FOR THREADING
            self.loop_body = transformed_body
            if isinstance(node.target, ast.Name):
                self.loop_target = node.target.id
            elif isinstance(node.target, (ast.Tuple, ast.List)):
                 # Handle idx, row unpacking
                 if len(node.target.elts) == 2 and isinstance(node.target.elts[1], ast.Name):
                     self.loop_target = node.target.elts[1].id
            
            return None # Remove the loop from main flow
            
        return self.generic_visit(node)


    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            name = self._get_func_name(node.value) # Keep old helper for simple calls
            if name in self.ignore_funcs or name in ['exit', 'quit']:
                return None
            if isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name):
                if node.value.func.value.id == 'sys' and node.value.func.attr == 'exit':
                    return None
        # if name == 'print': return None # ALLOW PRINTS for debugging
        if self._uses_removed_var(node.value):
             return None
        
        self.generic_visit(node)
        return node
        
    def _get_func_name(self, call_node):
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return None

    def _get_full_func_name(self, call_node):
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            # Try to resolve builtins/modules
            val = call_node.func.value
            if isinstance(val, ast.Name):
                return f"{val.id}.{call_node.func.attr}"
        return ""


    def _uses_removed_var(self, node):
        found = False
        class VarChecker(ast.NodeVisitor):
            def __init__(self, removed):
                self.removed = removed
                self.found = False
            def visit_Name(self, n):
                if n.id in self.removed:
                    self.found = True
        checker = VarChecker(self.removed_vars)
        checker.visit(node)
        return checker.found

class LoopControlReplacer(ast.NodeTransformer):
    """
    Replaces 'continue' with 'return idx, row' in the main loop body 
    when extracting it to a function. 
    """
    def __init__(self, target_var):
        self.target_var = target_var

    def visit_Continue(self, node):
        # Return idx, row (assuming 'idx' is in scope of the worker function)
        return ast.Return(value=ast.Tuple(elts=[
            ast.Name(id='idx', ctx=ast.Load()),
            ast.Name(id=self.target_var, ctx=ast.Load())
        ], ctx=ast.Load()))

    def visit_Break(self, node):
        # Treat break as return for threading context
        return ast.Return(value=ast.Tuple(elts=[
            ast.Name(id='idx', ctx=ast.Load()),
            ast.Name(id=self.target_var, ctx=ast.Load())
        ], ctx=ast.Load()))

    def visit_For(self, node):
        return node
    def visit_While(self, node):
        return node


class MainGuardReplacer(ast.NodeTransformer):
    def visit_If(self, node):
        if (isinstance(node.test, ast.Compare) and 
            isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__' and
            len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq) and
            len(node.test.comparators) == 1):
            comp = node.test.comparators[0]
            if isinstance(comp, (ast.Constant, ast.Str)) and (getattr(comp, 'value', '') == '__main__' or getattr(comp, 's', '') == '__main__'):
                node.test = ast.Constant(value=True)
        return self.generic_visit(node)

def convert_code(code, no_threading=False):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        sys.stderr.write(f"Conversion Syntax Error: {e}")
        sys.exit(1)

    cleaner = ScriptCleaner()
    cleaned_tree = cleaner.visit(tree)
    
    # ---------------------------------------------------------
    # 1. INJECTIONS (Imports & Globals)
    # ---------------------------------------------------------
    imports_to_add = [
        ast.Import(names=[ast.alias(name='builtins', asname=None)]),
        ast.Import(names=[ast.alias(name='concurrent.futures', asname=None)]),
        ast.Import(names=[ast.alias(name='requests', asname=None)]),
        ast.Import(names=[ast.alias(name='json', asname=None)]),
    ]
    
    has_pd = any(isinstance(n, ast.Import) and any(alias.name == 'pandas' for alias in n.names) for n in cleaned_tree.body)
    if not has_pd: 
        imports_to_add.insert(0, ast.Import(names=[ast.alias(name='pandas', asname='pd')]))

    # ---------------------------------------------------------
    # 2. WRAPPER UTILS
    # ---------------------------------------------------------
    wrapper_source = """
def _log_req(method, url, **kwargs):
    # import requests (Global)
    # import json (Global)
    
    
    def _debug_jwt(token_str):
        try:
            if not token_str or len(token_str) < 10: return "Invalid/Empty Token"
            if token_str.startswith("Bearer "): token_str = token_str.replace("Bearer ", "")
            parts = token_str.split('.')
            if len(parts) < 2: return "Not a JWT"
            payload = parts[1]
            pad = len(payload) % 4
            if pad: payload += '=' * (4 - pad)
            import base64
            decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
            claims = json.loads(decoded)
            user = claims.get('preferred_username') or claims.get('sub')
            iss = claims.get('iss', '')
            tenant = iss.split('/')[-1] if '/' in iss else 'Unknown'
            return f"User: {user} | Tenant: {tenant}"
        except Exception as e:
            return f"Decode Error: {e}"

    headers = kwargs.get('headers', {})
    auth_header = headers.get('Authorization', 'None')
    token_meta = _debug_jwt(auth_header)
    
    print(f"[API_DEBUG] ----------------------------------------------------------------")
    print(f"[API_DEBUG] 🚀 REQUEST: {method} {url}")
    print(f"[API_DEBUG] 🔑 TOKEN META: {token_meta}")
    
    payload = kwargs.get('json') or kwargs.get('data')
    
    # Multipart Support (DTO)
    if not payload:
        files = kwargs.get('files')
        if files and isinstance(files, dict):
             # Try to find 'dto' or 'body'
             if 'dto' in files:
                 # files['dto'] is usually (filename, content, content_type)
                 val = files['dto']
                 if isinstance(val, (list, tuple)) and len(val) > 1:
                     payload = f"[Multipart DTO] {val[1]}" 
                 else:
                     payload = f"[Multipart DTO] {val}"
             else:
                 # Just list keys
                 payload = f"[Multipart Files] Keys: {list(files.keys())}"
    
    if not payload: payload = "No Payload"
    print(f"[API_DEBUG] 📦 PAYLOAD: {payload}")
    print(f"[API_DEBUG] ----------------------------------------------------------------")

    try:
        if method == 'GET': resp = requests.get(url, **kwargs)
        elif method == 'POST': resp = requests.post(url, **kwargs)
        elif method == 'PUT': resp = requests.put(url, **kwargs)
        elif method == 'DELETE': resp = requests.delete(url, **kwargs)
        else: resp = requests.request(method, url, **kwargs)
        
        body_preview = "Binary/No Content"
        try:
             # Try to parse and pretty print JSON
             if not resp.text or not resp.text.strip():
                 body_preview = "[Empty Response]"
             else:
                 try:
                     json_obj = resp.json()
                     body_preview = json.dumps(json_obj, indent=2)
                 except:
                     # Fallback to text
                     body_preview = resp.text[:4000] # Increased limit
        except: 
             pass
        
        status_icon = "✅" if 200 <= resp.status_code < 300 else "❌"
        print(f"[API_DEBUG] {status_icon} RESPONSE [{resp.status_code}]")
        print(f"[API_DEBUG] 📄 BODY:\\n{body_preview}")
        print(f"[API_DEBUG] ----------------------------------------------------------------\\n")
        
        return resp
    except Exception as e:
        print(f"[API_DEBUG] ❌ EXCEPTION: {e}")
        print(f"[API_DEBUG] ----------------------------------------------------------------\\n")
        raise e

def _log_get(url, **kwargs): return _log_req('GET', url, **kwargs)
def _log_post(url, **kwargs): return _log_req('POST', url, **kwargs)
def _log_put(url, **kwargs): return _log_req('PUT', url, **kwargs)
def _log_delete(url, **kwargs): return _log_req('DELETE', url, **kwargs)

def _safe_iloc(row, idx):
    try:
        if isinstance(row, dict):
             # Dict access by index (ordered keys in Python 3.7+)
             keys = list(row.keys())
             if 0 <= idx < len(keys):
                 val = row[keys[idx]]
                 # Clean string if needed
                 return val.strip() if isinstance(val, str) else val
             return None
        elif isinstance(row, list):
             if 0 <= idx < len(row): return row[idx]
             return None
        # Fallback for actual pandas series if we ever support it fully
        return row.iloc[idx]
    except:
        return None
"""
    wrapper_nodes = ast.parse(wrapper_source).body

    # ---------------------------------------------------------
    # 3. SETUP CODE
    # ---------------------------------------------------------
    setup_code = """
import sys
sys.argv = [sys.argv[0]]

builtins.data = data
builtins.data_df = pd.DataFrame(data)

import os
valid_token_path = os.path.join(os.getcwd(), 'valid_token.txt')
if os.path.exists(valid_token_path):
    try:
        with open(valid_token_path, 'r') as f:
            forced_token = f.read().strip()
        if len(forced_token) > 10:
            print(f"[API_DEBUG] ⚠️ OVERRIDE: Using token from valid_token.txt")
            token = forced_token
    except Exception: pass
        
builtins.token = token
builtins.base_url = env_config.get('apiBaseUrl')
base_url = builtins.base_url
env_key = env_config.get('environment')
file_path = "Uploaded_File.xlsx" 
builtins.file_path = file_path
env_url = base_url 
builtins.env_url = base_url 

class MockCell:
    def __init__(self, row_data, key):
        self.row_data = row_data
        self.key = key
    @property
    def value(self): return self.row_data.get(self.key)
    @value.setter
    def value(self, val): self.row_data[self.key] = val

class MockSheet:
    def __init__(self, data): self.data = data
    def cell(self, row, column, value=None):
        idx = row - 2
        if not (0 <= idx < len(self.data)): return MockCell({}, "dummy")
        row_data = self.data[idx]
        keys = list(row_data.keys())
        if 1 <= column <= len(keys): key = keys[column - 1]
        elif 'output_columns' in dir(builtins) and 0 <= column-1 < len(builtins.output_columns):
             key = builtins.output_columns[column-1]
        else: key = f"Column_{column}"
        cell = MockCell(row_data, key)
        if value is not None: cell.value = value
        return cell
    @property
    def max_row(self): return len(self.data) + 1

class MockWorkbook:
    def __init__(self, data_or_builtins):
        if hasattr(data_or_builtins, 'data'): self.data = data_or_builtins.data
        else: self.data = data_or_builtins
    def __getitem__(self, key): return MockSheet(self.data)
    @property
    def sheetnames(self): return ["Sheet1", "Environment_Details", "Plot_details", "Sheet"]
    def save(self, path):
        import json
        print(f"[MOCK] Excel saved to {path}")
        try:
            print("[OUTPUT_DATA_DUMP]")
            print(json.dumps(self.data))
            print("[/OUTPUT_DATA_DUMP]")
        except: pass
    @property
    def active(self): return MockSheet(self.data)

wk = MockWorkbook(builtins)
builtins.wk = wk
builtins.wb = wk
wb = wk
"""
    setup_nodes = ast.parse(setup_code).body

    # Default Arg Transformation
    class DefaultArgTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            num_defaults = len(node.args.defaults)
            if num_defaults == 0: return self.generic_visit(node)
            offset = len(node.args.args) - num_defaults
            new_defaults = []
            assignments_to_inject = []
            for i, default_val in enumerate(node.args.defaults):
                arg_name = node.args.args[offset + i].arg
                is_literal = isinstance(default_val, (ast.Constant, ast.Str, ast.Num, ast.NameConstant))
                if not is_literal:
                    new_defaults.append(ast.Constant(value=None))
                    check_none = ast.If(
                        test=ast.Compare(
                            left=ast.Name(id=arg_name, ctx=ast.Load()),
                            ops=[ast.Is()],
                            comparators=[ast.Constant(value=None)]
                        ),
                        body=[ast.Assign(targets=[ast.Name(id=arg_name, ctx=ast.Store())], value=default_val)],
                        orelse=[]
                    )
                    assignments_to_inject.append(check_none)
                else:
                    new_defaults.append(default_val)
            node.args.defaults = new_defaults
            node.body = assignments_to_inject + node.body
            return self.generic_visit(node)

    cleaned_tree = DefaultArgTransformer().visit(cleaned_tree)
    ast.fix_missing_locations(cleaned_tree)

    # 4. RE-ASSEMBLY
    import_nodes = []
    constant_nodes = []
    definition_nodes = [] 
    execution_nodes = []
    main_guard_node = None
    
    def is_safe_expr(node):
        if isinstance(node, (ast.Constant, ast.Str, ast.Num, ast.NameConstant, ast.Bytes, ast.Ellipsis)): return True
        elif isinstance(node, ast.Name): return True 
        elif isinstance(node, ast.Attribute): return True 
        elif isinstance(node, ast.JoinedStr): return all(is_safe_expr(val) for val in node.values)
        elif isinstance(node, ast.FormattedValue): return is_safe_expr(node.value)
        elif isinstance(node, ast.BinOp): return is_safe_expr(node.left) and is_safe_expr(node.right)
        elif isinstance(node, (ast.List, ast.Tuple)): return all(is_safe_expr(elt) for elt in node.elts)
        elif isinstance(node, ast.Dict): return all(is_safe_expr(k) and is_safe_expr(v) for k, v in zip(node.keys, node.values))
        elif isinstance(node, ast.UnaryOp): return is_safe_expr(node.operand)
        return False

    def is_constant_assign(n):
        if not isinstance(n, ast.Assign): return False
        if len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name): return False
        return is_safe_expr(n.value)
    
    for node in cleaned_tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)): import_nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): definition_nodes.append(node)
        elif is_constant_assign(node): constant_nodes.append(node)
        elif isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
             if (isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__'): main_guard_node = node
             else: execution_nodes.append(node)
        else: execution_nodes.append(node)

    # ---------------------------------------------------------
    # 5. THREADING INJECTION
    # ---------------------------------------------------------
    if cleaner.loop_body:
        loop_target = cleaner.loop_target or 'row'
        
        # A. Create Process Worker Function
        # Apply LoopControlReplacer to loop body
        body_transformer = LoopControlReplacer(loop_target)
        threaded_body = []
        for stmt in cleaner.loop_body:
             transformed = body_transformer.visit(stmt)
             if isinstance(transformed, list): threaded_body.extend(transformed)
             elif transformed: threaded_body.append(transformed)
        
        # Append safe return at end
        threaded_body.append(ast.Return(value=ast.Tuple(elts=[
             ast.Name(id='idx', ctx=ast.Load()),
             ast.Name(id=loop_target, ctx=ast.Load())
        ], ctx=ast.Load())))

        process_func = ast.FunctionDef(
            name='process_row',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='idx'), ast.arg(arg=loop_target)],
                kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=threaded_body,
            decorator_list=[]
        )
        definition_nodes.append(process_func)

        # B. Create Executor Block (Threading vs Sequential)
        if not no_threading:
            executor_source = f"""
print(f"[Threaded] Starting execution with 5 workers...")
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    # Iterate over builtins.data (List of Dicts)
    futures = {{executor.submit(process_row, idx, row): idx for idx, row in enumerate(builtins.data)}}
    for future in concurrent.futures.as_completed(futures):
        try:
            res = future.result()
            # Result is (idx, row) - data is modifed in-place since row is a dict ref from builtins.data
        except Exception as e:
            print(f"[Threaded] Row failed: {{e}}")
"""
        else:
            # SEQUENTIAL SOURCE
            executor_source = f"""
print(f"[Sequential] Starting execution (Single Thread)...")
for idx, row in enumerate(builtins.data):
    try:
        process_row(idx, row)
    except Exception as e:
         print(f"[Sequential] Row {{idx}} failed: {{e}}")
"""

        executor_nodes = ast.parse(executor_source).body
        execution_nodes.extend(executor_nodes)

    # 6. CONSTRUCT 'RUN' BODY
    run_body = []
    run_body.extend(imports_to_add)
    run_body.extend(import_nodes)
    run_body.extend(wrapper_nodes)
    run_body.extend(setup_nodes)
    run_body.extend(constant_nodes)
    
    # Check if user defined a 'run' function
    user_run_node = None
    for node in definition_nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'run':
            user_run_node = node
            # Rename it to avoid conflict with the wrapper 'run'
            node.name = '_user_run'
            break
            
    run_body.extend(definition_nodes)
    run_body.extend(execution_nodes)
    
    if main_guard_node:
        main_guard_node.test = ast.Constant(value=True)
        run_body.append(main_guard_node)

    # If user provided a run function, return its result
    if user_run_node:
        # res = _user_run(data, token, env_config)
        assign_res = ast.Assign(
            targets=[ast.Name(id='res', ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id='_user_run', ctx=ast.Load()),
                args=[
                    ast.Name(id='data', ctx=ast.Load()),
                    ast.Name(id='token', ctx=ast.Load()),
                    ast.Name(id='env_config', ctx=ast.Load())
                ],
                keywords=[]
            )
        )
        run_body.append(assign_res)

        # Sync Logic (Inject After Run)
        sync_source = """
try:
    # Only sync if res is None (User didn't return anything explicit)
    if res is None and hasattr(builtins, 'data_df'):
        import pandas as pd
        if isinstance(builtins.data_df, pd.DataFrame):
            # Prioritize the DataFrame content as the source of truth
            res = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
except Exception as e:
    print(f"[Warn] Failed to sync data_df to result: {e}")
"""
        run_body.extend(ast.parse(sync_source).body)
        run_body.append(ast.Return(value=ast.Name(id='res', ctx=ast.Load())))
    else:
        # Default behavior: Sync data_df back to data, then return data
        sync_source = """
try:
    if hasattr(builtins, 'data_df'):
        import pandas as pd
        if isinstance(builtins.data_df, pd.DataFrame):
            # Convert NaN to None (null in JSON) for cleaner output
            data = builtins.data_df.where(pd.notnull(builtins.data_df), None).to_dict(orient='records')
except Exception as e:
    print(f"[Warn] Failed to sync data_df to data: {e}")
"""
        run_body.extend(ast.parse(sync_source).body)
        run_body.append(ast.Return(value=ast.Name(id='data', ctx=ast.Load())))

    run_func = ast.FunctionDef(
        name='run',
        args=ast.arguments(
             posonlyargs=[], 
             args=[ast.arg(arg='data'), ast.arg(arg='token'), ast.arg(arg='env_config')],
             kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=run_body,
        decorator_list=[]
    )
    
    final_module = ast.Module(body=[run_func], type_ignores=[])
    ast.fix_missing_locations(final_module)
    return ast.unparse(final_module)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-threading', action='store_true', help='Disable multithreading injection')
    args, unknown = parser.parse_known_args()

    try:
         sys.stdin.reconfigure(encoding='utf-8')
    except: pass
    
    # Read from pipeline (stdin) if not a file arg (simple piping)
    # The runner calls this with no args for stdin, but we added one now.
    
    code = sys.stdin.read()
    if code:
        print(convert_code(code, no_threading=args.no_threading))
