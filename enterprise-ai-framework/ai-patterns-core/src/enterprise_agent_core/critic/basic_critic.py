"""Basic critic implementation for sufficiency checking.

Evaluates whether retrieved content is sufficient to answer the query.
Uses heuristics; production would use LLM-based evaluation.
"""

import logging
from typing import Optional

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.retrieval import RetrievalResult
from ..contracts.critic import SufficiencyResult
from ..contracts.planning import QuerySpec, SearchMode

logger = logging.getLogger(__name__)


class BasicCritic:
    """Basic sufficiency critic implementation.

    Evaluates retrieved content using heuristics:
    - Score thresholds
    - Chunk count requirements
    - Coverage estimation

    For production, use LLM-based evaluation with the
    critic_sufficiency_v1 prompt.
    """

    def __init__(
        self,
        score_threshold: float = 0.7,
        min_chunks: int = 1,
        min_confidence: float = 0.5,
        llm_client: Optional[object] = None,
    ):
        """Initialize the critic.

        Args:
            score_threshold: Minimum chunk score to consider relevant
            min_chunks: Minimum number of relevant chunks needed
            min_confidence: Minimum confidence for sufficiency
            llm_client: Optional LLM client for intelligent evaluation
        """
        self.score_threshold = score_threshold
        self.min_chunks = min_chunks
        self.min_confidence = min_confidence
        self.llm_client = llm_client

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
            ctx: Current agent context

        Returns:
            SufficiencyResult with sufficiency decision and guidance
        """
        # Count high-quality chunks
        high_quality_chunks = [
            chunk for chunk in retrieval.chunks
            if chunk.score >= self.score_threshold
        ]

        # Calculate metrics
        total_chunks = len(retrieval.chunks)
        quality_count = len(high_quality_chunks)
        avg_score = (
            sum(c.score for c in retrieval.chunks) / total_chunks
            if total_chunks > 0 else 0
        )

        # Determine sufficiency
        sufficient = quality_count >= self.min_chunks
        confidence = min(avg_score, 1.0) if sufficient else avg_score * 0.5

        # Identify missing aspects if insufficient
        missing_aspects = []
        next_query_specs = []

        if not sufficient:
            missing_aspects = self._identify_gaps(
                request.user_query,
                retrieval,
                ctx
            )

            next_query_specs = self._suggest_next_queries(
                request.user_query,
                missing_aspects,
                ctx
            )

        # Determine recommendations
        should_expand = not sufficient and quality_count == 0
        should_change_source = not sufficient and total_chunks > 0 and avg_score < 0.3

        # Log decision
        logger.info(
            f"Critic decision: sufficient={sufficient}, "
            f"confidence={confidence:.2f}, "
            f"quality_chunks={quality_count}/{total_chunks}"
        )

        # Track prompt version
        ctx.prompt_versions["critic"] = "basic_v1"

        return SufficiencyResult(
            sufficient=sufficient,
            confidence=confidence,
            missing_aspects=missing_aspects,
            next_query_specs=next_query_specs,
            reasoning=self._generate_reasoning(
                sufficient, quality_count, total_chunks, avg_score
            ),
            coverage_estimate=avg_score if total_chunks > 0 else 0,
            relevance_scores=[c.score for c in retrieval.chunks[:5]],
            should_expand_query=should_expand,
            should_change_source=should_change_source,
            suggested_source="foundry_iq" if should_change_source else None,
        )

    def _identify_gaps(
        self,
        query: str,
        retrieval: RetrievalResult,
        ctx: AgentContext
    ) -> list[str]:
        """Identify aspects of the query not covered by retrieval.

        In production, this would use LLM analysis.
        """
        gaps = []

        if len(retrieval.chunks) == 0:
            gaps.append("No relevant content found for the query")
        elif all(c.score < 0.5 for c in retrieval.chunks):
            gaps.append("Retrieved content has low relevance")

        # Check if query has multiple aspects
        if " and " in query.lower():
            gaps.append("Query may require multiple topics to be addressed")

        return gaps

    def _suggest_next_queries(
        self,
        original_query: str,
        missing_aspects: list[str],
        ctx: AgentContext
    ) -> list[QuerySpec]:
        """Suggest queries for the next iteration.

        In production, this would use LLM-based query refinement.
        """
        next_specs = []

        # Expand the original query
        expanded_spec = QuerySpec(
            query_text=f"detailed information about: {original_query}",
            top_k=8,  # Increase results
            mode=SearchMode.HYBRID,
            rerank=True,
        )
        next_specs.append(expanded_spec)

        # If there are gaps, try a broader search
        if missing_aspects:
            # Extract key terms and search broadly
            broader_spec = QuerySpec(
                query_text=original_query,
                top_k=10,
                mode=SearchMode.SEMANTIC,  # Pure semantic for broader match
                rerank=True,
            )
            next_specs.append(broader_spec)

        return next_specs

    def _generate_reasoning(
        self,
        sufficient: bool,
        quality_count: int,
        total_count: int,
        avg_score: float
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        if sufficient:
            return (
                f"Found {quality_count} high-quality chunks "
                f"(avg score: {avg_score:.2f}). Content is sufficient."
            )
        else:
            if total_count == 0:
                return "No content retrieved. Need to expand search."
            elif quality_count == 0:
                return (
                    f"Retrieved {total_count} chunks but none meet "
                    f"quality threshold ({self.score_threshold}). "
                    f"Average score: {avg_score:.2f}."
                )
            else:
                return (
                    f"Only {quality_count} of {total_count} chunks "
                    f"meet quality threshold. Need more relevant content."
                )
