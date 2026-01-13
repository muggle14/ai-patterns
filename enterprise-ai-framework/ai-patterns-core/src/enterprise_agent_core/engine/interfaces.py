"""Legacy interfaces module.

Note: This module is deprecated. Use the interfaces from the
enterprise_agent_core.interfaces package instead:

- IEnterpriseRouter from interfaces.router
- IPlanner from interfaces.planner
- IRetriever from interfaces.retriever
- ICritic from interfaces.critic
- ISynthesizer from interfaces.synthesizer
- IToolExecutor from interfaces.tool_executor

This file is kept for backwards compatibility only.
"""

from ..contracts.response import AgentResponse
from ..interfaces.router import IEnterpriseRouter, RouteDecision

__all__ = [
    "AgentResponse",
    "IEnterpriseRouter",
    "RouteDecision",
]
