"""
Status Controller for the Old Fashioned Agent.

Returns the status and results of a job.
"""

from typing import Dict, Any, Optional

from ..utils.temp_db import get_job
from ..config.logger import Logger

logger = Logger()


def get_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a job.

    Args:
        job_id: The job identifier

    Returns:
        Status dictionary with job state and results if available
    """
    if not job_id:
        return {
            "error": "Job ID is required",
            "code": 400
        }

    try:
        job_data = get_job(job_id)

        if job_data is None:
            return {
                "id": job_id,
                "status": "not_found",
                "message": f"Job {job_id} not found"
            }

        return {
            "id": job_id,
            "status": job_data.get("status", "unknown"),
            "result": job_data.get("result"),
            "created_at": job_data.get("created_at")
        }

    except Exception as e:
        logger.error(f"Error getting status for job {job_id}: {str(e)}")
        return {
            "error": str(e),
            "code": 500
        }
