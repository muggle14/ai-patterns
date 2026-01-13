"""Synthesizer interface for response generation.

The synthesizer creates the final response from retrieved content,
including proper citations.
"""

from typing import Protocol, runtime_checkable

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.retrieval import RetrievalResult
from ..contracts.response import AgentResponse


@runtime_checkable
class ISynthesizer(Protocol):
    """Interface for response synthesis.

    The synthesizer takes retrieved content and generates:
    - A natural language response
    - Proper citations for sources used
    - Suggested follow-up questions

    This is the final step in the cognitive loop before
    optional tool execution.
    """

    async def write(
        self,
        request: AgentRequest,
        retrieval: RetrievalResult,
        ctx: AgentContext
    ) -> AgentResponse:
        """Synthesize a response from retrieved content.

        Args:
            request: Original agent request
            retrieval: Retrieved content chunks
            ctx: Current agent context (includes plan, critic results)

        Returns:
            AgentResponse with text, citations, and audit info
        """
        ...
