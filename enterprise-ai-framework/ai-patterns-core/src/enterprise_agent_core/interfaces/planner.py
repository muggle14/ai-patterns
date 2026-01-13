"""Planner interface for query decomposition.

The planner breaks down user queries into structured query plans
for Azure AI Search and Foundry IQ Knowledge Base retrieval.
"""

from typing import Protocol, runtime_checkable

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.planning import QueryPlan


@runtime_checkable
class IPlanner(Protocol):
    """Interface for query planning.

    The planner analyzes the user query and creates a structured
    query plan with:
    - Intent classification
    - Sub-question decomposition
    - Query specifications for retrieval

    Used in PLAN_RAG, FULL_ACTOR_CRITIC, and ACTION_GATED modes.
    Skipped in FAST_RAG mode.
    """

    async def plan(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> QueryPlan:
        """Create a query plan from the user's request.

        Args:
            request: The incoming agent request
            ctx: Current agent context (may contain history)

        Returns:
            QueryPlan with intents, subquestions, and query specs
        """
        ...
