"""Retriever interface for content retrieval.

The retriever executes queries against Azure AI Search, Foundry IQ
Knowledge Base, or other data sources.
"""

from typing import Protocol, runtime_checkable

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.planning import QueryPlan
from ..contracts.retrieval import RetrievalResult


@runtime_checkable
class IRetriever(Protocol):
    """Interface for content retrieval.

    The retriever executes the query plan against one or more
    data sources and returns relevant content chunks.

    Implementations:
    - AISearchDirectRetriever: Direct Azure AI Search queries
    - FoundryIQRetriever: Azure AI Foundry IQ Knowledge Base
    - ConfluenceApiRetriever: Confluence via Logic Apps
    - SharePointGraphRetriever: SharePoint via Graph API
    """

    async def retrieve(
        self,
        plan: QueryPlan,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RetrievalResult:
        """Execute retrieval based on the query plan.

        Args:
            plan: Query plan with specifications
            request: Original agent request
            ctx: Current agent context

        Returns:
            RetrievalResult with chunks and metrics
        """
        ...
