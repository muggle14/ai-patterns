"""Tool executor interface for action handling.

The tool executor validates and executes tool calls for
Logic Apps, ServiceNow, and other integrations.
"""

from typing import Protocol, runtime_checkable

from ..contracts.request import AgentContext
from ..contracts.tools import ToolCallRequest, ToolCallResult


@runtime_checkable
class IToolExecutor(Protocol):
    """Interface for tool execution.

    The tool executor:
    - Validates tool payloads against schemas
    - Handles approval flows (for ACTION_GATED mode)
    - Executes tool calls with timeout and retry
    - Records execution in audit logs

    Implementations may wrap:
    - Logic Apps
    - ServiceNow API
    - Azure Functions
    - Custom APIs
    """

    async def execute(
        self,
        tool_request: ToolCallRequest,
        ctx: AgentContext
    ) -> ToolCallResult:
        """Execute a tool call.

        Args:
            tool_request: Tool invocation request with payload
            ctx: Current agent context

        Returns:
            ToolCallResult with status and outputs
        """
        ...

    async def validate(
        self,
        tool_request: ToolCallRequest
    ) -> bool:
        """Validate a tool request before execution.

        Args:
            tool_request: Tool invocation request to validate

        Returns:
            True if valid, raises ValidationError if not
        """
        ...
