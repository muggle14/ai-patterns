"""Enterprise Agent Core Contracts.

All data contracts (Pydantic models) with schema versioning for the Enterprise AI Agent Framework.
Designed for Azure AI Foundry integration.
"""

from .base import BaseContract
from .request import RiskTier, AgentRequest, AgentContext
from .planning import QuerySpec, QueryPlan
from .retrieval import RetrievedChunk, RetrievalMetrics, RetrievalResult
from .critic import SufficiencyResult
from .tools import ToolCallRequest, ToolCallResult
from .governance import PiiMode, ContentSafetyMode, GovernanceRequest, GovernanceResult
from .response import Citation, ActionLog, AuditFields, AgentResponse

__all__ = [
    # Base
    "BaseContract",
    # Request
    "RiskTier",
    "AgentRequest",
    "AgentContext",
    # Planning
    "QuerySpec",
    "QueryPlan",
    # Retrieval
    "RetrievedChunk",
    "RetrievalMetrics",
    "RetrievalResult",
    # Critic
    "SufficiencyResult",
    # Tools
    "ToolCallRequest",
    "ToolCallResult",
    # Governance
    "PiiMode",
    "ContentSafetyMode",
    "GovernanceRequest",
    "GovernanceResult",
    # Response
    "Citation",
    "ActionLog",
    "AuditFields",
    "AgentResponse",
]
