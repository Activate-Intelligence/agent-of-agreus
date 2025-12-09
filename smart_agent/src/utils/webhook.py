"""
Webhook utilities for sending status updates and results.
"""

import os
import requests
from typing import Dict, Any, Optional
from smart_agent.src.config.logger import Logger

logger = Logger()

# Webhook URL from environment
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")


def call_webhook(
    job_id: Optional[str],
    payload: Dict[str, Any],
    timeout: int = 30
) -> bool:
    """
    Send a webhook callback with the given payload.

    Args:
        job_id: The job identifier
        payload: The data to send
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    if not WEBHOOK_URL:
        logger.debug(f"No webhook URL configured, skipping callback for job {job_id}")
        return True

    if not job_id:
        logger.warning("No job ID provided for webhook callback")
        return False

    try:
        full_payload = {
            "id": job_id,
            **payload
        }

        response = requests.post(
            WEBHOOK_URL,
            json=full_payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code >= 200 and response.status_code < 300:
            logger.debug(f"Webhook callback successful for job {job_id}")
            return True
        else:
            logger.warning(
                f"Webhook callback failed for job {job_id}: "
                f"Status {response.status_code}, Response: {response.text}"
            )
            return False

    except requests.Timeout:
        logger.error(f"Webhook callback timed out for job {job_id}")
        return False

    except requests.RequestException as e:
        logger.error(f"Webhook callback error for job {job_id}: {str(e)}")
        return False


def call_webhook_with_success(
    job_id: Optional[str],
    data: Dict[str, Any]
) -> bool:
    """
    Send a success webhook callback.

    Args:
        job_id: The job identifier
        data: The success data to send

    Returns:
        True if successful, False otherwise
    """
    return call_webhook(job_id, data)


def call_webhook_with_error(
    job_id: Optional[str],
    error_message: str,
    error_code: int = 500
) -> bool:
    """
    Send an error webhook callback.

    Args:
        job_id: The job identifier
        error_message: The error message
        error_code: The error code

    Returns:
        True if successful, False otherwise
    """
    payload = {
        "status": "error",
        "error": {
            "message": error_message,
            "code": error_code
        }
    }
    return call_webhook(job_id, payload)
