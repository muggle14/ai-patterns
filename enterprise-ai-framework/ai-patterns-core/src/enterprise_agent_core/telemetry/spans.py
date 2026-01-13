"""Span utilities for Enterprise Agent telemetry.

Provides helper functions for creating consistent OpenTelemetry
spans across the cognitive loop components.
"""

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

from .attributes import Attributes


class SpanNames:
    """Standard span names for the cognitive loop.

    Use these constants for consistent span naming across
    all components.
    """

    # Root span
    AGENT_HANDLE = "agent.handle"

    # Cognitive loop steps
    ROUTE = "agent.route"
    PLAN = "agent.plan"
    RETRIEVE = "agent.retrieve"
    CRITIC = "agent.critic"
    SYNTHESIZE = "agent.synthesize"

    # Tool execution (append tool name)
    TOOL_CALL = "agent.tool_call"

    # Sub-operations
    RETRIEVAL_QUERY = "agent.retrieve.query"
    RETRIEVAL_RERANK = "agent.retrieve.rerank"

    @classmethod
    def tool_span_name(cls, tool_name: str) -> str:
        """Get span name for a tool execution.

        Args:
            tool_name: Name of the tool

        Returns:
            Span name like "agent.tool_call.create_ticket"
        """
        return f"{cls.TOOL_CALL}.{tool_name}"


def create_tracer(name: str = "enterprise_agent_core") -> Tracer:
    """Create an OpenTelemetry tracer for the Enterprise Agent.

    Args:
        name: Tracer name (default: enterprise_agent_core)

    Returns:
        Configured tracer instance
    """
    return trace.get_tracer(name)


@contextmanager
def agent_span(
    name: str,
    correlation_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    tracer: Optional[Tracer] = None,
) -> Generator[Span, None, None]:
    """Context manager for creating agent spans with standard attributes.

    Automatically adds correlation_id and thread_id to all spans
    for distributed tracing.

    Args:
        name: Span name (use SpanNames constants)
        correlation_id: Request correlation ID
        thread_id: Azure AI Foundry thread ID
        attributes: Additional span attributes
        tracer: Optional custom tracer

    Yields:
        Active span for adding additional attributes

    Example:
        ```python
        with agent_span(
            SpanNames.RETRIEVE,
            correlation_id=ctx.correlation_id,
            thread_id=ctx.thread_id,
            attributes={"agent.retrieval.top_k": 5}
        ) as span:
            result = await retriever.retrieve(plan, request, ctx)
            span.set_attribute(Attributes.RETRIEVAL_HIT_COUNT, len(result.chunks))
        ```
    """
    _tracer = tracer or create_tracer()

    with _tracer.start_as_current_span(name) as span:
        # Add standard attributes
        if correlation_id:
            span.set_attribute(Attributes.CORRELATION_ID, correlation_id)
        if thread_id:
            span.set_attribute(Attributes.THREAD_ID, thread_id)

        # Add custom attributes
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)

        yield span


def set_span_error(
    span: Span,
    error: Exception,
    error_type: Optional[str] = None,
) -> None:
    """Record an error on a span.

    Args:
        span: The span to record error on
        error: The exception that occurred
        error_type: Optional error type classification
    """
    span.record_exception(error)
    span.set_attribute(Attributes.ERROR_MESSAGE, str(error))

    if error_type:
        span.set_attribute(Attributes.ERROR_TYPE, error_type)
    else:
        span.set_attribute(Attributes.ERROR_TYPE, type(error).__name__)


def add_retrieval_attributes(
    span: Span,
    source: str,
    index_name: Optional[str],
    top_k: int,
    hit_count: int,
    latency_ms: float,
    mode: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> None:
    """Add standard retrieval attributes to a span.

    Args:
        span: The span to add attributes to
        source: Retrieval source (e.g., "azure_ai_search")
        index_name: Search index name
        top_k: Number of results requested
        hit_count: Number of results returned
        latency_ms: Retrieval latency
        mode: Search mode (semantic, keyword, hybrid)
        filters: Applied filters
    """
    span.set_attribute(Attributes.RETRIEVAL_SOURCE, source)
    span.set_attribute(Attributes.RETRIEVAL_TOP_K, top_k)
    span.set_attribute(Attributes.RETRIEVAL_HIT_COUNT, hit_count)
    span.set_attribute(Attributes.RETRIEVAL_LATENCY_MS, latency_ms)

    if index_name:
        span.set_attribute(Attributes.RETRIEVAL_INDEX, index_name)
    if mode:
        span.set_attribute(Attributes.RETRIEVAL_MODE, mode)
    if filters:
        span.set_attribute(Attributes.RETRIEVAL_FILTERS, str(filters))


def add_critic_attributes(
    span: Span,
    sufficient: bool,
    confidence: float,
    missing_count: int,
) -> None:
    """Add standard critic attributes to a span.

    Args:
        span: The span to add attributes to
        sufficient: Whether retrieval was sufficient
        confidence: Confidence in the decision
        missing_count: Number of missing aspects
    """
    span.set_attribute(Attributes.CRITIC_SUFFICIENT, sufficient)
    span.set_attribute(Attributes.CRITIC_CONFIDENCE, confidence)
    span.set_attribute(Attributes.CRITIC_MISSING_COUNT, missing_count)


def add_tool_attributes(
    span: Span,
    tool_name: str,
    status: str,
    execution_ms: Optional[float] = None,
    approval_required: bool = False,
) -> None:
    """Add standard tool execution attributes to a span.

    Args:
        span: The span to add attributes to
        tool_name: Name of the tool
        status: Execution status
        execution_ms: Execution time in milliseconds
        approval_required: Whether approval was required
    """
    span.set_attribute(Attributes.TOOL_NAME, tool_name)
    span.set_attribute(Attributes.TOOL_STATUS, status)
    span.set_attribute(Attributes.TOOL_APPROVAL_REQUIRED, approval_required)

    if execution_ms is not None:
        span.set_attribute(Attributes.TOOL_EXECUTION_MS, execution_ms)
