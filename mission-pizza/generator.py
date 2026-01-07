"""
Phase 1: OpenAPI to MCP Generator

Reads an OpenAPI specification and generates a fully compliant MCP server.
This handles parameter parsing, schema extraction, and tool generation.
"""

import json
import requests
from typing import Any
from pathlib import Path


def fetch_openapi_spec(url: str) -> dict:
    """Fetch OpenAPI spec from a running server."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def sanitize_function_name(name: str) -> str:
    """Convert operation ID or path to valid Python function name."""
    name = name.replace("-", "_").replace("/", "_").replace("{", "").replace("}", "")
    while name and (name[0] == "_" or name[0].isdigit()):
        name = name[1:]
    return name.lower()


def get_python_type(schema: dict) -> str:
    """Convert OpenAPI schema type to Python type hint."""
    if not schema:
        return "str"
    
    schema_type = schema.get("type", "string")
    
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict"
    }
    
    return type_mapping.get(schema_type, "str")


def extract_parameters(operation: dict, path: str) -> list[dict]:
    """Extract parameters from operation and path."""
    params = []
    
    # Path parameters
    path_params = [p.strip("{}") for p in path.split("/") if p.startswith("{")]
    for param_name in path_params:
        params.append({
            "name": param_name,
            "type": "str",
            "required": True,
            "description": f"Path parameter: {param_name}",
            "location": "path"
        })
    
    # Query parameters
    for param in operation.get("parameters", []):
        if param.get("in") == "query":
            params.append({
                "name": param["name"],
                "type": get_python_type(param.get("schema", {})),
                "required": param.get("required", False),
                "description": param.get("description", ""),
                "location": "query"
            })
    
    # Request body
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})
    
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        params.append({
            "name": "_body_ref",
            "ref": ref_name,
            "location": "body"
        })
    elif schema.get("properties"):
        required_fields = schema.get("required", [])
        for prop_name, prop_schema in schema["properties"].items():
            params.append({
                "name": prop_name,
                "type": get_python_type(prop_schema),
                "required": prop_name in required_fields,
                "description": prop_schema.get("description", ""),
                "default": prop_schema.get("default"),
                "location": "body"
            })
    
    return params


def resolve_schema_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref to its schema definition."""
    parts = ref.replace("#/", "").split("/")
    schema = spec
    for part in parts:
        schema = schema.get(part, {})
    return schema


def generate_tool_function(
    func_name: str,
    method: str,
    path: str,
    operation: dict,
    params: list[dict],
    spec: dict
) -> str:
    """Generate a single MCP tool function."""
    
    description = operation.get("summary", operation.get("description", f"{method.upper()} {path}"))
    description = description.replace('"', '\\"').replace("\n", " ")
    
    # Resolve body references
    resolved_params = []
    for param in params:
        if param.get("ref"):
            ref_schema = resolve_schema_ref(spec, f"#/components/schemas/{param['ref']}")
            required_fields = ref_schema.get("required", [])
            for prop_name, prop_schema in ref_schema.get("properties", {}).items():
                resolved_params.append({
                    "name": prop_name,
                    "type": get_python_type(prop_schema),
                    "required": prop_name in required_fields,
                    "description": prop_schema.get("description", ""),
                    "default": prop_schema.get("default"),
                    "location": "body"
                })
        else:
            resolved_params.append(param)
    
    # Build function signature
    required_params = [p for p in resolved_params if p.get("required")]
    optional_params = [p for p in resolved_params if not p.get("required")]
    
    sig_parts = []
    for p in required_params:
        sig_parts.append(f"{p['name']}: {p['type']}")
    for p in optional_params:
        default = p.get("default")
        if default is None:
            default_str = "None"
            type_str = f"Optional[{p['type']}]"
        elif isinstance(default, str):
            default_str = f'"{default}"'
            type_str = p['type']
        else:
            default_str = str(default)
            type_str = p['type']
        sig_parts.append(f"{p['name']}: {type_str} = {default_str}")
    
    signature = ", ".join(sig_parts) if sig_parts else ""
    
    # Build URL
    url_template = path
    path_params = [p for p in resolved_params if p.get("location") == "path"]
    for p in path_params:
        url_template = url_template.replace("{" + p["name"] + "}", "' + str(" + p["name"] + ") + '")
    
    if url_template.startswith("'"):
        url_expr = f"BASE_URL + '{url_template}"
    else:
        url_expr = f"BASE_URL + '{url_template}'"
    
    url_expr = url_expr.replace("'' + ", "").replace(" + ''", "")
    
    # Build request code
    query_params = [p for p in resolved_params if p.get("location") == "query"]
    body_params = [p for p in resolved_params if p.get("location") == "body"]
    
    request_code = ""
    
    if query_params:
        request_code += "    params = {}\n"
        for p in query_params:
            request_code += f"    if {p['name']} is not None:\n"
            request_code += f"        params['{p['name']}'] = {p['name']}\n"
    
    if body_params:
        request_code += "    payload = {\n"
        for p in body_params:
            request_code += f"        \"{p['name']}\": {p['name']},\n"
        request_code += "    }\n"
        request_code += "    payload = {k: v for k, v in payload.items() if v is not None}\n"
    
    # HTTP call
    method_lower = method.lower()
    if method_lower == "get":
        if query_params:
            http_call = "response = httpx.get(url, params=params, timeout=30)"
        else:
            http_call = "response = httpx.get(url, timeout=30)"
    elif method_lower == "post":
        http_call = "response = httpx.post(url, json=payload, timeout=30)"
    elif method_lower == "patch":
        if body_params:
            http_call = "response = httpx.patch(url, json=payload, timeout=30)"
        else:
            http_call = "response = httpx.patch(url, timeout=30)"
    elif method_lower == "delete":
        http_call = "response = httpx.delete(url, timeout=30)"
    elif method_lower == "put":
        http_call = "response = httpx.put(url, json=payload, timeout=30)"
    else:
        http_call = f"response = httpx.request('{method_lower}', url, timeout=30)"
    
    read_only = method_lower == "get"
    destructive = method_lower in ["delete", "patch"]
    
    function_code = f'''
@mcp.tool(
    name="{func_name}",
    annotations={{
        "readOnlyHint": {read_only},
        "destructiveHint": {destructive}
    }}
)
async def {func_name}({signature}) -> str:
    """
    {description}
    """
    url = {url_expr}
{request_code}
    try:
        {http_call}
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({{"error": str(e), "status_code": e.response.status_code}})
    except Exception as e:
        return json.dumps({{"error": str(e)}})
'''
    
    return function_code


def generate_mcp_server(spec: dict, base_url: str, output_path: str):
    """Generate the complete MCP server file."""
    
    header = f'''"""
Auto-generated MCP Server from OpenAPI Specification.

Generated from: {spec.get("info", {}).get("title", "Unknown API")}
Version: {spec.get("info", {}).get("version", "1.0.0")}
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import httpx
import json

mcp = FastMCP("pizza_mcp")

BASE_URL = "{base_url}"
'''
    
    tools_code = ""
    
    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                operation_id = operation.get("operationId")
                if operation_id:
                    func_name = sanitize_function_name(operation_id)
                else:
                    func_name = sanitize_function_name(f"{method}_{path}")
                
                params = extract_parameters(operation, path)
                tools_code += generate_tool_function(
                    func_name, method, path, operation, params, spec
                )
    
    footer = '''

if __name__ == "__main__":
    mcp.run()
'''
    
    full_code = header + tools_code + footer
    
    with open(output_path, "w") as f:
        f.write(full_code)
    
    print(f"Generated MCP server: {output_path}")
    return full_code


def main():
    """Main entry point."""
    import sys
    
    openapi_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/openapi.json"
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "generated_mcp_server.py"
    
    print(f"Fetching OpenAPI spec from {openapi_url}...")
    spec = fetch_openapi_spec(openapi_url)
    
    print("Generating MCP server...")
    generate_mcp_server(spec, base_url, output_path)
    
    print("Done.")


if __name__ == "__main__":
    main()
