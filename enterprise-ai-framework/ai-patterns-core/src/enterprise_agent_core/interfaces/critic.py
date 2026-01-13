"""Critic interface for sufficiency checking.

The critic evaluates whether retrieved content is sufficient
to answer the user's query in the actor-critic loop.
"""

from typing import Protocol, runtime_checkable

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.retrieval import RetrievalResult
from ..contracts.critic import SufficiencyResult


@runtime_checkable
class ICritic(Protocol):
    """Interface for sufficiency checking.

    The critic evaluates the retrieved content and determines:
    - Whether it's sufficient to answer the query
    - What aspects are missing
    - What additional queries might help

    Used in FULL_ACTOR_CRITIC and ACTION_GATED modes.
    Drives the actor-critic loop iteration.
    """

    async def check(
        self,
        request: AgentRequest,
        retrieval: RetrievalResult,
        ctx: AgentContext
    ) -> SufficiencyResult:
        """Check if retrieved content is sufficient.

        Args:
            request: Original agent request
            retrieval: Retrieved content chunks
            ctx: Current agent context (includes plan)

        Returns:
            SufficiencyResult indicating if more retrieval is needed
        """
        ...
