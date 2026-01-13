"""Basic synthesizer implementation for response generation.

Generates responses with proper citations from retrieved content.
For production, uses LLM with citation_format_v1 prompt.
"""

import logging
from typing import Optional

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.retrieval import RetrievalResult
from ..contracts.response import AgentResponse, Citation

logger = logging.getLogger(__name__)


class BasicSynthesizer:
    """Basic response synthesizer implementation.

    Generates responses from retrieved content with:
    - Proper citations
    - Suggested follow-ups
    - Quality indicators

    For production, integrate with Azure OpenAI using
    the citation_format_v1 prompt template.
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
        model_deployment: str = "gpt-4o",
        max_response_tokens: int = 1000,
    ):
        """Initialize the synthesizer.

        Args:
            llm_client: Azure OpenAI client for generation
            model_deployment: Model deployment name
            max_response_tokens: Maximum tokens in response
        """
        self.llm_client = llm_client
        self.model_deployment = model_deployment
        self.max_response_tokens = max_response_tokens

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
            ctx: Current agent context

        Returns:
            AgentResponse with text, citations, and audit info
        """
        # Build citations from high-quality chunks
        citations = self._build_citations(retrieval)

        # Generate response text
        if self.llm_client:
            response_text = await self._generate_with_llm(
                request.user_query,
                retrieval,
                ctx
            )
        else:
            response_text = self._generate_basic_response(
                request.user_query,
                retrieval
            )

        # Generate suggested follow-ups
        followups = self._generate_followups(request.user_query, retrieval)

        # Track prompt version
        ctx.prompt_versions["synthesizer"] = "basic_v1"

        logger.info(
            f"Generated response with {len(citations)} citations, "
            f"{len(response_text)} chars"
        )

        return AgentResponse(
            thread_id=request.thread_id,
            response_text=response_text,
            citations=citations,
            suggested_followups=followups,
        )

    def _build_citations(self, retrieval: RetrievalResult) -> list[Citation]:
        """Build citations from retrieved chunks."""
        citations = []

        for chunk in retrieval.chunks:
            # Only cite chunks with reasonable confidence
            if chunk.score >= 0.5:
                citation = Citation(
                    content_id=chunk.content_id,
                    url=chunk.url,
                    title=chunk.title,
                    snippet=chunk.snippet[:300],  # Truncate for display
                    confidence_score=chunk.score,
                    source_system=chunk.source_system,
                )
                citations.append(citation)

        # Limit to top 5 citations
        return sorted(
            citations,
            key=lambda c: c.confidence_score,
            reverse=True
        )[:5]

    def _generate_basic_response(
        self,
        query: str,
        retrieval: RetrievalResult
    ) -> str:
        """Generate a basic response without LLM.

        This is a fallback/mock implementation.
        Production should always use LLM generation.
        """
        if not retrieval.chunks:
            return (
                "I couldn't find relevant information to answer your question. "
                "Please try rephrasing your query or contact support for assistance."
            )

        # Build response from top chunks
        top_chunks = sorted(
            retrieval.chunks,
            key=lambda c: c.score,
            reverse=True
        )[:3]

        response_parts = [
            f"Based on the available information:\n"
        ]

        for i, chunk in enumerate(top_chunks, 1):
            response_parts.append(f"\n[{i}] {chunk.snippet[:500]}")

        response_parts.append(
            "\n\nPlease refer to the cited sources for more details."
        )

        return "".join(response_parts)

    async def _generate_with_llm(
        self,
        query: str,
        retrieval: RetrievalResult,
        ctx: AgentContext
    ) -> str:
        """Generate response using Azure OpenAI.

        This would use the citation_format_v1 prompt template.
        """
        # Placeholder for LLM integration
        # In production:
        # 1. Build prompt with query and context
        # 2. Include citation instructions
        # 3. Call Azure OpenAI
        # 4. Parse and format response

        # For now, use basic generation
        return self._generate_basic_response(query, retrieval)

    def _generate_followups(
        self,
        query: str,
        retrieval: RetrievalResult
    ) -> list[str]:
        """Generate suggested follow-up questions."""
        followups = []

        # Generic follow-ups based on query type
        query_lower = query.lower()

        if "policy" in query_lower:
            followups.append("What are the exceptions to this policy?")
            followups.append("Who should I contact for policy questions?")
        elif "process" in query_lower or "how" in query_lower:
            followups.append("What are the prerequisites for this process?")
            followups.append("Where can I find related documentation?")
        else:
            followups.append("Can you provide more details?")
            followups.append("Are there any related topics I should know about?")

        return followups[:3]
