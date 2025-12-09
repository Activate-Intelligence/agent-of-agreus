"""
Request validators for the Old Fashioned Agent.
"""

from typing import Dict, Any, List, Optional, Tuple


def validate_execute_request(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate an execute request.

    Args:
        data: Request data dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    inputs = data.get("inputs", [])

    if not isinstance(inputs, list):
        return False, "inputs must be a list"

    # Check for required payload input
    payload_found = False
    for inp in inputs:
        if not isinstance(inp, dict):
            return False, "Each input must be a dictionary"

        if "name" not in inp:
            return False, "Each input must have a 'name' field"

        if inp.get("name") == "payload":
            payload_found = True
            if not inp.get("data"):
                return False, "payload input cannot be empty"

    if not payload_found:
        return False, "Missing required input: payload"

    return True, None


def validate_abort_request(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate an abort request.

    Args:
        data: Request data dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if "id" not in data:
        return False, "id is required"

    if not data.get("id"):
        return False, "id cannot be empty"

    return True, None


def validate_status_request(job_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a status request.

    Args:
        job_id: The job ID to check

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not job_id:
        return False, "id is required"

    return True, None
