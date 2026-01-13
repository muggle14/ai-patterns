"""Enterprise Agent Core Interfaces.

Protocol definitions for all swappable components in the Enterprise AI Agent Framework.
These enable fungibility - swap implementations without changing the engine.
"""

from .router import IEnterpriseRouter, RouteDecision
from .planner import IPlanner
from .retriever import IRetriever
from .critic import ICritic
from .synthesizer import ISynthesizer
from .tool_executor import IToolExecutor

__all__ = [
    "IEnterpriseRouter",
    "RouteDecision",
    "IPlanner",
    "IRetriever",
    "ICritic",
    "ISynthesizer",
    "IToolExecutor",
]
