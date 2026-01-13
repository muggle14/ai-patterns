"""Enterprise Agent Core - Azure AI Foundry Agent Framework.

A production-ready framework for building enterprise AI agents with:
- Deterministic cognitive loop (Plan -> Retrieve -> Critic -> Synthesize -> Act)
- Swappable components (routers, retrievers, tools)
- Full observability (OpenTelemetry spans)
- Azure AI Foundry integration

Example:
    ```python
    from enterprise_agent_core.api import create_app
    from enterprise_agent_core.config import load_config_from_yaml

    config = load_config_from_yaml("agent.yaml")
    app = create_app(config)
    ```
"""

__version__ = "1.0.0"

# Core contracts
from .contracts import (
    AgentRequest,
    AgentContext,
    AgentResponse,
    QueryPlan,
    QuerySpec,
    RetrievalResult,
    RetrievedChunk,
    SufficiencyResult,
    ToolCallRequest,
    ToolCallResult,
    GovernanceRequest,
    GovernanceResult,
    Citation,
    ActionLog,
    AuditFields,
)

# Configuration
from .config import (
    AgentConfig,
    KnowledgeConfig,
    GovernanceConfig,
    LoopMode,
    LoopBudget,
    load_config_from_yaml,
)

# Engine
from .engine import AgentWorkflowEngine

# Interfaces
from .interfaces import (
    IEnterpriseRouter,
    IPlanner,
    IRetriever,
    ICritic,
    ISynthesizer,
    IToolExecutor,
    RouteDecision,
)

__all__ = [
    # Version
    "__version__",
    # Contracts
    "AgentRequest",
    "AgentContext",
    "AgentResponse",
    "QueryPlan",
    "QuerySpec",
    "RetrievalResult",
    "RetrievedChunk",
    "SufficiencyResult",
    "ToolCallRequest",
    "ToolCallResult",
    "GovernanceRequest",
    "GovernanceResult",
    "Citation",
    "ActionLog",
    "AuditFields",
    # Config
    "AgentConfig",
    "KnowledgeConfig",
    "GovernanceConfig",
    "LoopMode",
    "LoopBudget",
    "load_config_from_yaml",
    # Engine
    "AgentWorkflowEngine",
    # Interfaces
    "IEnterpriseRouter",
    "IPlanner",
    "IRetriever",
    "ICritic",
    "ISynthesizer",
    "IToolExecutor",
    "RouteDecision",
]
