"""
FastAPI routes for the Old Fashioned Agent.

Defines endpoints: /discover, /execute, /status, /abort, /logs
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from smart_agent.src.controllers.ExecuteController import execute
from smart_agent.src.controllers.DiscoverController import discover
from smart_agent.src.controllers.StatusController import get_status
from smart_agent.src.controllers.AbortController import abort

router = APIRouter()


# Request/Response Models
class InputItem(BaseModel):
    name: str
    data: Any


class ExecuteRequest(BaseModel):
    id: Optional[str] = None
    inputs: List[InputItem] = Field(default_factory=list)


class AbortRequest(BaseModel):
    id: str


# Routes
@router.get("/discover")
async def discover_endpoint():
    """
    Discovery endpoint for A2A protocol.
    Returns the agent.json configuration.
    """
    result = discover()
    if "error" in result:
        raise HTTPException(status_code=result.get("code", 500), detail=result["error"])
    return result


@router.post("/execute")
async def execute_endpoint(request: ExecuteRequest):
    """
    Execute the agent with the provided inputs.

    Inputs:
    - payload (required): The user's question or request
    - instructions (optional): Specific instructions for the query
    - threadId (optional): Thread ID for conversation continuity
    """
    # Convert Pydantic models to dicts
    inputs_list = [{"name": inp.name, "data": inp.data} for inp in request.inputs]

    result = execute({
        "id": request.id,
        "inputs": inputs_list
    })

    if "error" in result:
        raise HTTPException(status_code=result.get("code", 500), detail=result["error"])

    return result


@router.get("/status")
async def status_endpoint(id: str = Query(..., description="Job ID")):
    """
    Get the status of a job.
    """
    result = get_status(id)
    if "error" in result:
        raise HTTPException(status_code=result.get("code", 500), detail=result["error"])
    return result


@router.post("/abort")
async def abort_endpoint(request: AbortRequest):
    """
    Abort a running job.
    """
    result = abort(request.id)
    if "error" in result:
        raise HTTPException(status_code=result.get("code", 500), detail=result["error"])
    return result


@router.get("/logs")
async def logs_endpoint(id: str = Query(..., description="Job ID")):
    """
    Get logs for a job.
    """
    # For now, logs are included in status response
    result = get_status(id)
    if "error" in result:
        raise HTTPException(status_code=result.get("code", 500), detail=result["error"])
    return {
        "id": id,
        "logs": result.get("result", {}).get("logs", []),
        "status": result.get("status")
    }


@router.get("/health")
async def health_endpoint():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}
