"""
Abort Controller for the Old Fashioned Agent.

Handles job cancellation requests.
"""

from typing import Dict, Any

from ..utils.temp_db import get_job, update_job_status, delete_job
from ..utils.webhook import call_webhook_with_error
from ..config.logger import Logger

logger = Logger()


def abort(job_id: str) -> Dict[str, Any]:
    """
    Abort a running job.

    Args:
        job_id: The job identifier to abort

    Returns:
        Response dictionary indicating abort status
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

        current_status = job_data.get("status", "unknown")

        # Can only abort pending or running jobs
        if current_status in ["completed", "error", "aborted"]:
            return {
                "id": job_id,
                "status": current_status,
                "message": f"Job cannot be aborted - current status: {current_status}"
            }

        # Update status to aborted
        update_job_status(job_id, "aborted", {"reason": "User requested abort"})

        # Send webhook notification
        call_webhook_with_error(job_id, "Job aborted by user", 499)

        logger.info(f"Job {job_id} aborted")

        return {
            "id": job_id,
            "status": "aborted",
            "message": "Job aborted successfully"
        }

    except Exception as e:
        logger.error(f"Error aborting job {job_id}: {str(e)}")
        return {
            "error": str(e),
            "code": 500
        }
