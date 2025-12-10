"""
Thread storage utilities using DynamoDB for persistent conversation history.

Stores conversation threads by UUID, allowing multi-turn conversations
to persist across Lambda cold starts and instances.
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError

from smart_agent.src.config.logger import Logger

logger = Logger()

# DynamoDB configuration
THREADS_TABLE = os.environ.get("THREADS_TABLE", "agent-threads")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

# In-memory fallback for local development or when DynamoDB unavailable
_local_threads: Dict[str, List[Dict[str, str]]] = {}

# Lazy-loaded DynamoDB resource
_dynamodb = None


def get_dynamodb():
    """Get DynamoDB resource (lazy initialization)."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    return _dynamodb


def get_threads_table():
    """Get DynamoDB threads table resource."""
    dynamodb = get_dynamodb()
    return dynamodb.Table(THREADS_TABLE)


def get_thread(thread_id: str) -> List[Dict[str, str]]:
    """
    Retrieve conversation history from DynamoDB by thread UUID.

    Args:
        thread_id: UUID string identifying the conversation thread

    Returns:
        List of message dictionaries with 'role' and 'content' keys,
        or empty list if not found
    """
    if not thread_id:
        return []

    # Try DynamoDB first
    try:
        table = get_threads_table()
        response = table.get_item(Key={"thread_id": thread_id})

        if "Item" in response:
            messages_json = response["Item"].get("messages", "[]")
            messages = json.loads(messages_json)
            logger.info(f"Retrieved thread {thread_id} from DynamoDB: {len(messages)} messages")
            return messages

        logger.info(f"Thread {thread_id} not found in DynamoDB")
        return []

    except ClientError as e:
        logger.warning(f"DynamoDB error getting thread {thread_id}: {e}")
        # Fall back to local storage
        return _local_threads.get(thread_id, [])

    except Exception as e:
        logger.error(f"Unexpected error getting thread {thread_id}: {e}")
        return _local_threads.get(thread_id, [])


def save_thread(thread_id: Optional[str], messages: List[Dict[str, str]]) -> str:
    """
    Save conversation history to DynamoDB.

    Args:
        thread_id: Existing UUID to update, or None to create new thread
        messages: List of message dictionaries with 'role' and 'content'

    Returns:
        UUID string identifying the conversation thread
    """
    # Generate new UUID if needed
    if not thread_id:
        thread_id = str(uuid.uuid4())
        logger.info(f"Created new thread: {thread_id}")

    # Try DynamoDB first
    try:
        table = get_threads_table()

        item = {
            "thread_id": thread_id,
            "messages": json.dumps(messages, ensure_ascii=False),
            "message_count": len(messages),
            "updated_at": datetime.utcnow().isoformat(),
            "ttl": int((datetime.utcnow() + timedelta(days=30)).timestamp())  # 30-day TTL
        }

        table.put_item(Item=item)
        logger.info(f"Saved thread {thread_id} to DynamoDB: {len(messages)} messages")
        return thread_id

    except ClientError as e:
        logger.warning(f"DynamoDB error saving thread {thread_id}: {e}")
        # Fall back to local storage
        _local_threads[thread_id] = messages
        logger.info(f"Saved thread {thread_id} to local storage (fallback)")
        return thread_id

    except Exception as e:
        logger.error(f"Unexpected error saving thread {thread_id}: {e}")
        _local_threads[thread_id] = messages
        return thread_id


def delete_thread(thread_id: str) -> bool:
    """
    Delete a thread from DynamoDB.

    Args:
        thread_id: UUID of the thread to delete

    Returns:
        True if successful, False otherwise
    """
    if not thread_id:
        return False

    try:
        table = get_threads_table()
        table.delete_item(Key={"thread_id": thread_id})
        logger.info(f"Deleted thread {thread_id}")

        # Also remove from local cache if present
        if thread_id in _local_threads:
            del _local_threads[thread_id]

        return True

    except ClientError as e:
        logger.error(f"Failed to delete thread {thread_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error deleting thread {thread_id}: {e}")
        return False
