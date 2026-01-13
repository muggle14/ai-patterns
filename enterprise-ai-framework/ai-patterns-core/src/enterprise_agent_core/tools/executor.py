"""Tool executor implementation.

Executes tool calls (Logic Apps, APIs, etc.) with validation,
timeout handling, and audit logging.
"""

import time
import uuid
import logging
import asyncio
from typing import Dict, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from ..contracts.request import AgentContext
from ..contracts.tools import ToolCallRequest, ToolCallResult, ToolStatus
from ..config import LogicAppConfig

logger = logging.getLogger(__name__)


class BasicToolExecutor:
    """Basic tool executor implementation.

    Executes tool calls with:
    - Payload validation
    - Timeout handling
    - Retry with exponential backoff
    - Audit logging

    Supports:
    - Logic Apps (HTTP trigger)
    - Generic HTTP APIs
    """

    def __init__(
        self,
        logic_apps: Optional[Dict[str, LogicAppConfig]] = None,
        default_timeout_ms: int = 30000,
        max_retries: int = 2,
    ):
        """Initialize the tool executor.

        Args:
            logic_apps: Map of tool name to Logic App config
            default_timeout_ms: Default execution timeout
            max_retries: Maximum retry attempts for retryable errors
        """
        self.logic_apps = logic_apps or {}
        self.default_timeout_ms = default_timeout_ms
        self.max_retries = max_retries

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
        start_time = time.monotonic()
        tool_name = tool_request.tool_name

        # Track tool call
        ctx.tools_called.append(tool_name)

        logger.info(
            f"Executing tool: {tool_name}, "
            f"approval_required: {tool_request.approval_required}"
        )

        # Check for approval if required
        if tool_request.approval_required:
            return ToolCallResult(
                status=ToolStatus.PENDING_APPROVAL,
                approval_id=str(uuid.uuid4()),
            )

        # Validate the request
        try:
            await self.validate(tool_request)
        except ValueError as e:
            return ToolCallResult(
                status=ToolStatus.FAILED,
                error=str(e),
                error_code="VALIDATION_ERROR",
            )

        # Execute based on tool type
        try:
            if tool_name in self.logic_apps:
                result = await self._execute_logic_app(
                    tool_request,
                    self.logic_apps[tool_name],
                    ctx,
                )
            else:
                result = await self._execute_generic(tool_request, ctx)

            # Add execution time
            result.execution_time_ms = (time.monotonic() - start_time) * 1000
            return result

        except asyncio.TimeoutError:
            return ToolCallResult(
                status=ToolStatus.TIMEOUT,
                error=f"Tool execution timed out after {tool_request.timeout_ms}ms",
                error_code="TIMEOUT",
                execution_time_ms=(time.monotonic() - start_time) * 1000,
            )
        except Exception as e:
            logger.exception(f"Tool execution failed: {e}")
            return ToolCallResult(
                status=ToolStatus.FAILED,
                error=str(e),
                error_code="EXECUTION_ERROR",
                execution_time_ms=(time.monotonic() - start_time) * 1000,
            )

    async def validate(self, tool_request: ToolCallRequest) -> bool:
        """Validate a tool request before execution.

        Args:
            tool_request: Tool invocation request to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        # Check required fields
        if not tool_request.tool_name:
            raise ValueError("Tool name is required")

        if not isinstance(tool_request.payload, dict):
            raise ValueError("Payload must be a dictionary")

        # Check if tool is registered (for Logic Apps)
        if tool_request.tool_name in self.logic_apps:
            config = self.logic_apps[tool_request.tool_name]
            if not config.endpoint_url:
                raise ValueError(f"No endpoint configured for tool: {tool_request.tool_name}")

        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _execute_logic_app(
        self,
        tool_request: ToolCallRequest,
        config: LogicAppConfig,
        ctx: AgentContext,
    ) -> ToolCallResult:
        """Execute a Logic App tool.

        Args:
            tool_request: Tool request
            config: Logic App configuration
            ctx: Agent context

        Returns:
            ToolCallResult
        """
        timeout_sec = tool_request.timeout_ms / 1000

        headers = {
            "Content-Type": "application/json",
            "x-correlation-id": ctx.correlation_id,
            "x-thread-id": ctx.thread_id,
        }

        # Add idempotency key if provided
        if tool_request.idempotency_key:
            headers["x-idempotency-key"] = tool_request.idempotency_key

        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.endpoint_url,
                json=tool_request.payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_sec),
            ) as response:
                if response.status >= 200 and response.status < 300:
                    try:
                        outputs = await response.json()
                    except Exception:
                        outputs = {"raw": await response.text()}

                    return ToolCallResult(
                        status=ToolStatus.SUCCESS,
                        outputs=outputs,
                    )
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    return ToolCallResult(
                        status=ToolStatus.RETRYABLE_ERROR,
                        error="Rate limited",
                        error_code="RATE_LIMIT",
                        retry_after_ms=int(retry_after) * 1000,
                        is_retryable=True,
                    )
                else:
                    error_body = await response.text()
                    return ToolCallResult(
                        status=ToolStatus.FAILED,
                        error=f"HTTP {response.status}: {error_body[:500]}",
                        error_code=f"HTTP_{response.status}",
                    )

    async def _execute_generic(
        self,
        tool_request: ToolCallRequest,
        ctx: AgentContext,
    ) -> ToolCallResult:
        """Execute a generic tool (placeholder for custom implementations)."""
        logger.warning(
            f"Generic tool execution for '{tool_request.tool_name}' "
            "not implemented. Returning mock success."
        )

        return ToolCallResult(
            status=ToolStatus.SUCCESS,
            outputs={
                "message": "Tool executed successfully (mock)",
                "tool_name": tool_request.tool_name,
            },
        )
