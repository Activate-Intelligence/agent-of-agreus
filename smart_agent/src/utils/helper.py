"""
Helper utilities for the agent.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def extract_input_value(
    inputs: List[Dict[str, Any]],
    name: str,
    default: Any = None
) -> Any:
    """
    Extract a value from the inputs list by name.

    Args:
        inputs: List of input dictionaries with 'name' and 'data' keys
        name: The name of the input to find
        default: Default value if not found

    Returns:
        The input value or default
    """
    for input_item in inputs:
        if input_item.get('name') == name:
            return input_item.get('data', default)
    return default


def format_output(
    name: str,
    data: Any,
    output_type: str = "longText"
) -> Dict[str, Any]:
    """
    Format an output value for the response.

    Args:
        name: Output field name
        data: Output data
        output_type: Type of the output

    Returns:
        Formatted output dictionary
    """
    return {
        "name": name,
        "type": output_type,
        "data": data
    }


def validate_required_inputs(
    inputs: List[Dict[str, Any]],
    required_fields: List[str]
) -> tuple[bool, Optional[str]]:
    """
    Validate that all required inputs are present.

    Args:
        inputs: List of input dictionaries
        required_fields: List of required field names

    Returns:
        Tuple of (is_valid, error_message)
    """
    input_names = {inp.get('name') for inp in inputs}

    for field in required_fields:
        if field not in input_names:
            return False, f"Missing required input: {field}"

        value = extract_input_value(inputs, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, f"Required input '{field}' is empty"

    return True, None


def safe_get_env(key: str, default: str = "") -> str:
    """
    Safely get an environment variable.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.environ.get(key, default)
