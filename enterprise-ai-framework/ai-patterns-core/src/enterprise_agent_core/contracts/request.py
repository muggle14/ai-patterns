"""Request and context contracts for Enterprise Agent.

These contracts define the input structure for agent requests and the
context object that flows through the cognitive loop.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract


class RiskTier(str, Enum):
    """Risk classification for requests.

    Used for audit logging and future governance enforcement.
    """
    TIER1 = "tier1"  # Low risk - fast path, minimal logging
    TIER2 = "tier2"  # Medium risk - standard path, full logging
    TIER3 = "tier3"  # High risk - full audit, may require approval


class AgentRequest(BaseContract):
    """Incoming request to the Enterprise Agent.

    This is the primary input contract for the /chat endpoint.
    Supports Azure AI Foundry thread management and W3C trace propagation.
    """

    request_id: str = Field(..., description="Unique identifier for this request")
    thread_id: str = Field(..., description="Azure AI Foundry thread ID for conversation continuity")
    user_query: str = Field(..., description="The user's question or command")

    # Optional context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (e.g., incident_id, document_id)"
    )

    # Risk and governance
    risk_tier: RiskTier = Field(
        default=RiskTier.TIER2,
        description="Risk classification for this request"
    )

    # Trace context for distributed tracing (W3C format)
    trace_context: Optional[Dict[str, str]] = Field(
        default=None,
        description="W3C trace context (traceparent, tracestate) for end-to-end tracing"
    )

    # Access control placeholders (for future per-user trimming)
    user_id: Optional[str] = Field(default=None, description="User OID for access control")
    access_groups: List[str] = Field(
        default_factory=list,
        description="User's group memberships for retrieval filtering"
    )


class AgentContext(BaseContract):
    """Mutable context that flows through the cognitive loop.

    This object accumulates state as the request moves through:
    Plan -> Retrieve -> Critic -> Synthesize -> (Act)

    Each step reads from and writes to this context.
    """

    # Tracing
    correlation_id: str = Field(..., description="Unique ID for this request trace")
    thread_id: str = Field(..., description="Azure AI Foundry thread ID")

    # W3C distributed trace context
    trace_context: Dict[str, str] = Field(
        default_factory=dict,
        description="W3C trace context for distributed tracing"
    )

    # Loop state
    iteration: int = Field(default=0, description="Current actor-critic loop iteration")

    # Step outputs (populated as loop progresses)
    plan: Optional[Any] = Field(default=None, description="QueryPlan from planner")
    retrieval: Optional[Any] = Field(default=None, description="RetrievalResult from retriever")
    critic: Optional[Any] = Field(default=None, description="SufficiencyResult from critic")
    draft: Optional[str] = Field(default=None, description="Draft response before finalization")
    final: Optional[Any] = Field(default=None, description="Final AgentResponse")

    # Conversation history (for multi-turn)
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Previous turns in this thread"
    )

    # Telemetry accumulation
    data_sources_used: List[str] = Field(
        default_factory=list,
        description="Data sources accessed (Confluence, SharePoint, FoundryIQ, etc.)"
    )
    tools_called: List[str] = Field(
        default_factory=list,
        description="Tools invoked during this request"
    )
    prompt_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Prompt name -> version mapping for audit"
    )
