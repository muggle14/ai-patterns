"""Response contracts for agent output.

These contracts define the structure of agent responses including
citations, action logs, and audit fields for Azure AI Foundry.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract
from .governance import GovernanceResult
from .retrieval import RetrievalMetrics


class Citation(BaseContract):
    """Citation for a source used in the response.

    Maps to Azure AI Foundry citation format for UI rendering.
    """

    content_id: str = Field(..., description="Source content identifier")
    url: Optional[str] = Field(default=None, description="URL to source document")
    title: Optional[str] = Field(default=None, description="Document title")
    snippet: str = Field(..., description="Relevant excerpt from source")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that this source supports the response"
    )

    # Source metadata
    source_system: Optional[str] = Field(
        default=None,
        description="Source system (confluence, sharepoint, foundry_iq)"
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number if applicable"
    )


class ActionLog(BaseContract):
    """Log entry for a tool action taken.

    Records tool invocations for audit and debugging.
    """

    tool_name: str = Field(..., description="Name of the tool executed")
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters (may be redacted)"
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Output values (may be redacted)"
    )
    status: str = Field(default="success", description="Execution status")

    # Timing
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Execution duration"
    )

    # Approval tracking
    required_approval: bool = Field(
        default=False,
        description="Whether approval was required"
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="Approver if applicable"
    )


class AuditFields(BaseContract):
    """Audit fields for compliance and debugging.

    Captures all information needed for audit trail and debugging.
    """

    # Request tracking
    correlation_id: str = Field(..., description="Unique request correlation ID")
    thread_id: str = Field(..., description="Azure AI Foundry thread ID")
    request_id: str = Field(..., description="Original request ID")

    # Agent identification
    agent_name: str = Field(..., description="Name of the agent")
    project_name: Optional[str] = Field(default=None, description="Project name")

    # Risk tracking
    risk_tier: str = Field(default="tier2", description="Risk tier applied")

    # Data access
    data_sources_used: List[str] = Field(
        default_factory=list,
        description="Data sources accessed"
    )

    # Tool usage
    tools_called: List[str] = Field(
        default_factory=list,
        description="Tools that were invoked"
    )

    # Prompt tracking
    prompt_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Prompt name to version mapping"
    )

    # Loop tracking
    loop_mode: str = Field(..., description="Loop mode used")
    iterations_used: int = Field(default=1, description="Actor-critic iterations")

    # Access control (placeholder)
    user_id: Optional[str] = Field(default=None, description="User OID")
    access_groups: List[str] = Field(
        default_factory=list,
        description="User's access groups"
    )


class AgentResponse(BaseContract):
    """Complete response from the Enterprise Agent.

    This is the primary output contract returned from /chat.
    Includes response text, citations, actions, and full audit trail.
    """

    # Core response
    thread_id: str = Field(..., description="Azure AI Foundry thread ID")
    response_text: str = Field(..., description="The agent's response to the user")

    # Loop mode used
    response_mode: str = Field(
        default="plan_rag",
        description="Loop mode used (fast_rag, plan_rag, full_actor_critic, action_gated)"
    )

    # Citations
    citations: List[Citation] = Field(
        default_factory=list,
        description="Sources cited in the response"
    )

    # Actions
    actions_taken: List[ActionLog] = Field(
        default_factory=list,
        description="Tools/actions executed"
    )

    # Performance
    processing_time_ms: float = Field(
        default=0.0,
        description="Total processing time"
    )

    # Retrieval metrics
    retrieval_metrics: Optional[RetrievalMetrics] = Field(
        default=None,
        description="Retrieval performance metrics"
    )

    # Governance
    governance_result: Optional[GovernanceResult] = Field(
        default=None,
        description="Governance check results"
    )

    # Full audit trail
    audit: Optional[AuditFields] = Field(
        default=None,
        description="Complete audit information"
    )

    # Conversation continuity
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions"
    )
