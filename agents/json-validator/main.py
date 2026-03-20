"""JSON Validator Agent - Validates JSON data."""
import json

async def run(inputs: dict) -> dict:
    json_str = inputs.get("json", "")
    schema = inputs.get("schema")
    
    errors = []
    valid = True
    
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        valid = False
        errors.append(f"Invalid JSON: {str(e)}")
    
    return {
        "valid": valid,
        "errors": errors,
        "status": "success"
    }
