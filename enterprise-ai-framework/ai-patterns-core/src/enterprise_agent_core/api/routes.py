"""API routes for Enterprise Agent.

Defines the REST endpoints for the agent including:
- POST /chat - Main agent interaction endpoint
- GET /healthz - Liveness probe
- GET /readyz - Readiness probe
"""

import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..contracts.request import AgentRequest
from ..contracts.response import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str = "1.0.0"


class ReadyResponse(BaseModel):
    """Readiness check response."""
    status: str
    checks: dict


@router.post("/chat", response_model=AgentResponse)
async def chat(
    request: AgentRequest,
    http_request: Request,
) -> AgentResponse:
    """Process a chat request through the cognitive loop.

    This is the main endpoint for interacting with the Enterprise Agent.
    It accepts an AgentRequest and returns an AgentResponse with:
    - Response text
    - Citations
    - Actions taken
    - Audit information

    Args:
        request: The agent request with user query and context
        http_request: FastAPI request object for accessing app state

    Returns:
        AgentResponse with response, citations, and audit trail

    Raises:
        HTTPException: If processing fails
    """
    start_time = time.monotonic()

    # Get engine from app state
    engine = getattr(http_request.app.state, "engine", None)
    if not engine:
        logger.error("Engine not initialized in app state")
        raise HTTPException(
            status_code=503,
            detail="Agent engine not initialized"
        )

    try:
        logger.info(
            f"Processing chat request: request_id={request.request_id}, "
            f"thread_id={request.thread_id}"
        )

        response = await engine.handle(request)

        processing_time = (time.monotonic() - start_time) * 1000
        logger.info(
            f"Chat request completed: request_id={request.request_id}, "
            f"processing_time_ms={processing_time:.0f}"
        )

        return response

    except Exception as e:
        logger.exception(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe for container orchestration.

    Returns 200 if the service is alive.
    Used by Azure Container Apps for liveness checks.
    """
    return HealthResponse(status="healthy")


@router.get("/readyz", response_model=ReadyResponse)
async def readyz(http_request: Request) -> ReadyResponse:
    """Readiness probe for container orchestration.

    Checks if all dependencies are ready:
    - Engine initialized
    - (Future) Azure AI Search reachable
    - (Future) Azure OpenAI reachable

    Returns 200 if ready to accept traffic.
    Used by Azure Container Apps for readiness checks.
    """
    checks = {}

    # Check engine
    engine = getattr(http_request.app.state, "engine", None)
    checks["engine"] = "ok" if engine else "not_initialized"

    # Check config
    config = getattr(http_request.app.state, "config", None)
    checks["config"] = "ok" if config else "not_loaded"

    # Overall status
    all_ok = all(v == "ok" for v in checks.values())

    if not all_ok:
        raise HTTPException(
            status_code=503,
            detail=ReadyResponse(status="not_ready", checks=checks).model_dump()
        )

    return ReadyResponse(status="ready", checks=checks)


@router.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "Enterprise Agent API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /healthz",
            "ready": "GET /readyz",
        }
    }
