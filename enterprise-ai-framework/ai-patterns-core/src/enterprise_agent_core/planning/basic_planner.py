"""Basic planner implementation.

Provides a simple planner that converts user queries into QueryPlans.
For production, this would use an LLM for intelligent decomposition.
"""

import logging
from typing import Optional

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.planning import QueryPlan, QuerySpec, SearchMode

logger = logging.getLogger(__name__)


class BasicPlanner:
    """Basic query planner implementation.

    Converts user queries into structured QueryPlans with:
    - Intent classification (simple heuristics)
    - Query specification generation

    For production use, replace with LLM-based planning that can:
    - Decompose complex queries into sub-questions
    - Identify required data sources
    - Determine optimal search strategies
    """

    def __init__(
        self,
        default_top_k: int = 5,
        default_mode: SearchMode = SearchMode.HYBRID,
        llm_client: Optional[object] = None,
    ):
        """Initialize the planner.

        Args:
            default_top_k: Default number of results to retrieve
            default_mode: Default search mode
            llm_client: Optional LLM client for intelligent planning
        """
        self.default_top_k = default_top_k
        self.default_mode = default_mode
        self.llm_client = llm_client

    async def plan(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> QueryPlan:
        """Create a query plan from the user's request.

        Args:
            request: The incoming agent request
            ctx: Current agent context

        Returns:
            QueryPlan with intents and query specifications
        """
        # Classify intent using simple heuristics
        intents = self._classify_intent(request.user_query)

        # Check for comparison request
        requires_comparison = self._check_comparison(request.user_query)

        # Generate query specifications
        query_specs = self._generate_query_specs(
            request.user_query,
            intents,
            request.metadata,
        )

        # Log planning
        logger.info(
            f"Generated plan with {len(query_specs)} query specs, "
            f"intents: {intents}"
        )

        # Track prompt version
        ctx.prompt_versions["planner"] = "basic_v1"

        return QueryPlan(
            intents=intents,
            subquestions=[request.user_query],  # Basic: no decomposition
            query_specs=query_specs,
            requires_multi_source=len(intents) > 1,
            requires_comparison=requires_comparison,
        )

    def _classify_intent(self, query: str) -> list[str]:
        """Classify the query intent using simple heuristics.

        In production, this would use an LLM or classifier.
        """
        query_lower = query.lower()
        intents = []

        # Information retrieval intent
        if any(word in query_lower for word in [
            "what", "how", "explain", "describe", "tell me",
            "find", "search", "show", "list", "policy", "process"
        ]):
            intents.append("information_retrieval")

        # Action intent
        if any(word in query_lower for word in [
            "create", "update", "delete", "add", "remove",
            "submit", "request", "open", "close", "ticket"
        ]):
            intents.append("action_request")

        # Comparison intent
        if any(word in query_lower for word in [
            "compare", "difference", "versus", "vs", "between"
        ]):
            intents.append("comparison")

        # Default to information retrieval
        if not intents:
            intents.append("information_retrieval")

        return intents

    def _check_comparison(self, query: str) -> bool:
        """Check if the query requires document comparison."""
        query_lower = query.lower()
        return any(word in query_lower for word in [
            "compare", "difference", "versus", "vs",
            "v1", "v2", "version 1", "version 2", "old and new"
        ])

    def _generate_query_specs(
        self,
        query: str,
        intents: list[str],
        metadata: dict,
    ) -> list[QuerySpec]:
        """Generate query specifications for retrieval.

        Args:
            query: The user query
            intents: Classified intents
            metadata: Request metadata (may contain filters)

        Returns:
            List of QuerySpec for retrieval
        """
        specs = []

        # Build filters from metadata
        filters = {}
        if "space" in metadata:
            filters["space"] = metadata["space"]
        if "doc_type" in metadata:
            filters["doc_type"] = metadata["doc_type"]

        # Primary query spec
        primary_spec = QuerySpec(
            query_text=query,
            source_preference=metadata.get("source_preference"),
            filters=filters,
            top_k=self.default_top_k,
            mode=self.default_mode,
            rerank=True,  # Enable semantic reranking
        )
        specs.append(primary_spec)

        # For action requests, add a policy lookup
        if "action_request" in intents:
            policy_spec = QuerySpec(
                query_text=f"policy guidelines for: {query}",
                source_preference="confluence",
                filters={"doc_type": "policy"},
                top_k=3,
                mode=SearchMode.SEMANTIC,
            )
            specs.append(policy_spec)

        return specs
