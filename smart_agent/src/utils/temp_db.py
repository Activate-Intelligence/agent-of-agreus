"""
Temporary database utilities using DynamoDB for job state storage.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from smart_agent.src.config.logger import Logger

logger = Logger()

# DynamoDB configuration
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "agent-jobs")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# In-memory fallback for local development
_local_db: Dict[str, Dict[str, Any]] = {}


def get_dynamodb_client():
    """Get DynamoDB client."""
    return boto3.resource('dynamodb', region_name=AWS_REGION)


def get_table():
    """Get DynamoDB table resource."""
    dynamodb = get_dynamodb_client()
    return dynamodb.Table(DYNAMODB_TABLE)


def save_job(job_id: str, data: Dict[str, Any]) -> bool:
    """
    Save job data to DynamoDB.

    Args:
        job_id: The job identifier
        data: Job data to save

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_table()

        item = {
            "id": job_id,
            "data": json.dumps(data),
            "created_at": datetime.utcnow().isoformat(),
            "ttl": int((datetime.utcnow() + timedelta(days=7)).timestamp())
        }

        table.put_item(Item=item)
        logger.debug(f"Saved job {job_id} to DynamoDB")
        return True

    except ClientError as e:
        logger.error(f"Failed to save job {job_id} to DynamoDB: {e}")
        # Fall back to local storage
        _local_db[job_id] = {
            "data": data,
            "created_at": datetime.utcnow().isoformat()
        }
        return True

    except Exception as e:
        logger.error(f"Unexpected error saving job {job_id}: {e}")
        _local_db[job_id] = {
            "data": data,
            "created_at": datetime.utcnow().isoformat()
        }
        return True


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job data from DynamoDB.

    Args:
        job_id: The job identifier

    Returns:
        Job data dictionary or None if not found
    """
    try:
        table = get_table()
        response = table.get_item(Key={"id": job_id})

        if "Item" in response:
            item = response["Item"]
            return json.loads(item.get("data", "{}"))

        return None

    except ClientError as e:
        logger.error(f"Failed to get job {job_id} from DynamoDB: {e}")
        # Fall back to local storage
        if job_id in _local_db:
            return _local_db[job_id].get("data")
        return None

    except Exception as e:
        logger.error(f"Unexpected error getting job {job_id}: {e}")
        if job_id in _local_db:
            return _local_db[job_id].get("data")
        return None


def update_job_status(job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> bool:
    """
    Update job status in DynamoDB.

    Args:
        job_id: The job identifier
        status: New status
        result: Optional result data

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_table()

        update_expression = "SET #status = :status, updated_at = :updated_at"
        expression_values = {
            ":status": status,
            ":updated_at": datetime.utcnow().isoformat()
        }
        expression_names = {"#status": "status"}

        if result:
            update_expression += ", #result = :result"
            expression_values[":result"] = json.dumps(result)
            expression_names["#result"] = "result"

        table.update_item(
            Key={"id": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values
        )

        logger.debug(f"Updated job {job_id} status to {status}")
        return True

    except ClientError as e:
        logger.error(f"Failed to update job {job_id} status: {e}")
        # Fall back to local storage
        if job_id in _local_db:
            _local_db[job_id]["status"] = status
            if result:
                _local_db[job_id]["result"] = result
        return True

    except Exception as e:
        logger.error(f"Unexpected error updating job {job_id}: {e}")
        return False


def delete_job(job_id: str) -> bool:
    """
    Delete job from DynamoDB.

    Args:
        job_id: The job identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        table = get_table()
        table.delete_item(Key={"id": job_id})
        logger.debug(f"Deleted job {job_id}")
        return True

    except ClientError as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        if job_id in _local_db:
            del _local_db[job_id]
        return True

    except Exception as e:
        logger.error(f"Unexpected error deleting job {job_id}: {e}")
        return False
