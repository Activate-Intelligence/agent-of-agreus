"""
Execute Controller for the Old Fashioned Agent.

Handles execution requests and returns structured responses with
output, explanation, and thread ID for conversation continuity.
"""

import asyncio
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from smart_agent.src.agent.base_agent import base_agent
from smart_agent.src.utils.webhook import call_webhook_with_success, call_webhook_with_error
from smart_agent.src.utils.helper import extract_input_value, generate_job_id
from smart_agent.src.utils.temp_db import save_job, update_job_status
from smart_agent.src.config.logger import Logger

logger = Logger()

# Thread pool for async execution
executor = ThreadPoolExecutor(max_workers=4)


def execute_sync(
    job_id: str,
    inputs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Synchronously execute the agent.

    Args:
        job_id: The job identifier
        inputs: List of input dictionaries

    Returns:
        Result dictionary
    """
    try:
        # Extract inputs
        payload = extract_input_value(inputs, 'payload', '')
        instructions = extract_input_value(inputs, 'instructions')
        thread_id = extract_input_value(inputs, 'threadId')

        if not payload:
            error_msg = "Missing required input: payload"
            call_webhook_with_error(job_id, error_msg, 400)
            return {"error": error_msg, "code": 400}

        # Prepare payload for base_agent
        agent_payload = {
            "id": job_id,
            "payload": payload,
            "instructions": instructions,
            "threadId": thread_id
        }

        # Execute agent
        resp, explanation, new_thread_id = base_agent(agent_payload)

        # Send completion webhook
        call_webhook_with_success(job_id, {
            "status": "completed",
            "data": {
                "output": resp
            }
        })

        # Update job status
        update_job_status(job_id, "completed", {
            "output": resp,
            "explanation": explanation,
            "threadId": new_thread_id
        })

        return {
            "result": resp,
            "explanation": explanation,
            "threadId": new_thread_id
        }

    except Exception as e:
        logger.error(f"Execution error for job {job_id}: {str(e)}")
        call_webhook_with_error(job_id, str(e), 500)
        update_job_status(job_id, "error", {"error": str(e)})
        return {"error": str(e), "code": 500}


async def execute_async(
    job_id: str,
    inputs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Asynchronously execute the agent.

    Args:
        job_id: The job identifier
        inputs: List of input dictionaries

    Returns:
        Result dictionary
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, execute_sync, job_id, inputs)


def execute(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main execute entry point.

    Args:
        request_data: Request data containing inputs and optional id

    Returns:
        Response dictionary with job_id and initial status
    """
    # Get or generate job ID
    job_id = request_data.get('id') or generate_job_id()
    inputs = request_data.get('inputs', [])

    # Save job to database
    save_job(job_id, {
        "inputs": inputs,
        "status": "pending"
    })

    # For synchronous execution (default for Lambda)
    result = execute_sync(job_id, inputs)

    return {
        "id": job_id,
        "status": "completed" if "error" not in result else "error",
        **result
    }


async def execute_background(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute agent in background (for async endpoints).

    Args:
        request_data: Request data

    Returns:
        Response with job_id for status polling
    """
    job_id = request_data.get('id') or generate_job_id()
    inputs = request_data.get('inputs', [])

    # Save job to database
    save_job(job_id, {
        "inputs": inputs,
        "status": "pending"
    })

    # Start async execution
    asyncio.create_task(execute_async(job_id, inputs))

    return {
        "id": job_id,
        "status": "pending",
        "message": "Job started"
    }
