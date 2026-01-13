"""Tool execution contracts for action handling.

These contracts define the structure for tool invocation requests
and results, supporting Logic Apps, ServiceNow, and other integrations.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract


class ToolStatus(str, Enum):
    """Status of a tool execution."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    RETRYABLE_ERROR = "retryable_error"


class ToolCallRequest(BaseContract):
    """Request to execute a tool (Logic App, API, etc.).

    Includes validation metadata and approval flow support
    for ACTION_GATED mode.
    """

    # Tool identification
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_schema_version: str = Field(
        default="1.0.0",
        description="Version of the tool's input schema"
    )

    # Payload
    payload: Dict[str, Any] = Field(
        ...,
        description="Tool input parameters (validated against schema)"
    )

    # Idempotency and safety
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Idempotency key for safe retries"
    )

    # Approval flow
    approval_required: bool = Field(
        default=False,
        description="Whether human approval is needed before execution"
    )
    approval_reason: Optional[str] = Field(
        default=None,
        description="Reason approval is required"
    )

    # Context for tool execution
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for context"
    )

    # Timeout configuration
    timeout_ms: int = Field(
        default=30000,
        description="Execution timeout in milliseconds"
    )


class ToolCallResult(BaseContract):
    """Result of a tool execution.

    Captures the outcome, outputs, and any errors from
    tool invocation.
    """

    # Status
    status: ToolStatus = Field(..., description="Execution status")

    # Outputs
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool outputs on success"
    )

    # Error handling
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code for programmatic handling"
    )

    # Retry guidance
    retry_after_ms: Optional[int] = Field(
        default=None,
        description="Milliseconds to wait before retry (if retryable)"
    )
    is_retryable: bool = Field(
        default=False,
        description="Whether the error is retryable"
    )

    # Execution metadata
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Actual execution time"
    )

    # For approval flow
    approval_id: Optional[str] = Field(
        default=None,
        description="Approval request ID if pending"
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="User who approved (if applicable)"
    )
