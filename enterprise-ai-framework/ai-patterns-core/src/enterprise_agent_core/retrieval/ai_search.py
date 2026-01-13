"""Azure AI Search Direct Retriever.

Provides direct access to Azure AI Search with full control over
query parameters (filters, facets, top_k, semantic config).

Async Implementation:
- Uses asyncio.to_thread() to run sync SearchClient in thread pool
- Supports bounded parallel retrieval across multiple QuerySpecs
- Merge/dedupe with stable sort by score

Production implementation uses azure-search-documents SDK.
"""

import asyncio
import time
import logging
from typing import Optional, List

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

from ..contracts.request import AgentRequest, AgentContext
from ..contracts.planning import QueryPlan, QuerySpec, SearchMode
from ..contracts.retrieval import (
    RetrievalResult,
    RetrievedChunk,
    RetrievalMetrics,
)
from ..config import KnowledgeConfig

logger = logging.getLogger(__name__)


class AISearchDirectRetriever:
    """Azure AI Search direct retriever.

    Provides full control over Azure AI Search queries with:
    - Semantic search with server-side vectorization
    - Hybrid search (semantic + keyword)
    - Filters and facets
    - Semantic reranking
    - Non-blocking async via asyncio.to_thread()
    - Bounded parallel retrieval with configurable concurrency

    When mock_mode=True, returns mocked data for development.
    Set mock_mode=False and provide credentials for real Azure calls.
    """

    # Maximum concurrent search requests
    MAX_CONCURRENT_SEARCHES = 3

    def __init__(
        self,
        config: Optional[KnowledgeConfig] = None,
        search_endpoint: Optional[str] = None,
        index_name: Optional[str] = None,
        credential: Optional[object] = None,
        mock_mode: bool = True,
    ):
        """Initialize the retriever.

        Args:
            config: KnowledgeConfig with search settings
            search_endpoint: Azure AI Search endpoint (overrides config)
            index_name: Search index name (overrides config)
            credential: Azure credential (DefaultAzureCredential if not provided)
            mock_mode: If True, return mocked data instead of real calls
        """
        self.config = config or KnowledgeConfig()
        self.search_endpoint = search_endpoint or self.config.search_endpoint
        self.index_name = index_name or self.config.index_name
        self.mock_mode = mock_mode

        # Initialize client for real mode
        self._client = None
        if not mock_mode and self.search_endpoint and self.index_name:
            self._init_client(credential)

    def _init_client(self, credential: Optional[object] = None):
        """Initialize the Azure AI Search client."""
        try:
            from azure.search.documents import SearchClient

            cred = credential or DefaultAzureCredential()
            self._client = SearchClient(
                endpoint=self.search_endpoint,
                index_name=self.index_name,
                credential=cred,
            )
            logger.info(
                f"Initialized AI Search client for index: {self.index_name}"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize search client: {e}")
            self.mock_mode = True

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
        start_time = time.monotonic()

        if self.mock_mode:
            result = await self._mock_retrieve(plan, request)
        else:
            result = await self._real_retrieve(plan, request, ctx)

        # Calculate total latency
        latency_ms = (time.monotonic() - start_time) * 1000
        result.metrics.latency_ms = latency_ms

        # Track source
        if "azure_ai_search" not in ctx.data_sources_used:
            ctx.data_sources_used.append("azure_ai_search")

        logger.info(
            f"Retrieved {len(result.chunks)} chunks in {latency_ms:.0f}ms"
        )

        return result

    async def _mock_retrieve(
        self,
        plan: QueryPlan,
        request: AgentRequest
    ) -> RetrievalResult:
        """Return mocked retrieval results for development."""
        # Generate mock chunks based on query
        mock_chunks = [
            RetrievedChunk(
                content_id="mock-doc-001",
                title="HR Policy: Vacation and Time Off",
                url="https://confluence.example.com/hr/vacation-policy",
                snippet=(
                    "Employees are entitled to 15 days of paid vacation per year. "
                    "Vacation requests must be submitted at least 2 weeks in advance "
                    "through the HR portal. Unused vacation days can be carried over "
                    "up to a maximum of 5 days to the following year."
                ),
                score=0.92,
                source_system="azure_ai_search",
                index_name=self.index_name or "mock-index",
                metadata={"doc_type": "policy", "space": "HR"},
            ),
            RetrievedChunk(
                content_id="mock-doc-002",
                title="Employee Handbook: Leave Policies",
                url="https://sharepoint.example.com/hr/handbook#leave",
                snippet=(
                    "In addition to vacation time, employees may take sick leave, "
                    "personal days, and family leave as outlined in this handbook. "
                    "Sick leave is provided at 10 days per year and does not carry over."
                ),
                score=0.85,
                source_system="azure_ai_search",
                index_name=self.index_name or "mock-index",
                metadata={"doc_type": "handbook", "space": "HR"},
            ),
            RetrievedChunk(
                content_id="mock-doc-003",
                title="FAQ: Common HR Questions",
                url="https://confluence.example.com/hr/faq",
                snippet=(
                    "Q: How do I request time off? A: Use the HR portal to submit "
                    "your request. Your manager will be notified automatically. "
                    "Q: What happens to unused vacation? A: Up to 5 days carry over."
                ),
                score=0.78,
                source_system="azure_ai_search",
                index_name=self.index_name or "mock-index",
                metadata={"doc_type": "faq", "space": "HR"},
            ),
        ]

        return RetrievalResult(
            chunks=mock_chunks,
            metrics=RetrievalMetrics(
                latency_ms=0,  # Will be set by caller
                hit_count=len(mock_chunks),
                total_available=10,
                source="azure_ai_search_mock",
                index_name=self.index_name or "mock-index",
                search_mode="hybrid",
            ),
            sources_queried=["azure_ai_search"],
        )

    async def _real_retrieve(
        self,
        plan: QueryPlan,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RetrievalResult:
        """Execute real Azure AI Search queries with bounded parallelism.
        
        Uses asyncio.Semaphore to limit concurrent search requests and
        asyncio.to_thread() to avoid blocking the event loop.
        """
        # Bounded parallel retrieval
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SEARCHES)
        
        async def bounded_query(spec: QuerySpec) -> List[RetrievedChunk]:
            async with semaphore:
                return await self._execute_query(spec, request)
        
        # Execute all queries in parallel with bounded concurrency
        tasks = [bounded_query(spec) for spec in plan.query_specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect chunks, logging any errors
        all_chunks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Query {i} failed: {result}")
            else:
                all_chunks.extend(result)

        # Deduplicate by content_id, preserving order (first occurrence wins)
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            if chunk.content_id not in seen_ids:
                seen_ids.add(chunk.content_id)
                unique_chunks.append(chunk)

        # Stable sort by score descending
        unique_chunks.sort(key=lambda c: (c.score, c.content_id), reverse=True)

        return RetrievalResult(
            chunks=unique_chunks,
            metrics=RetrievalMetrics(
                latency_ms=0,  # Will be set by caller
                hit_count=len(unique_chunks),
                source="azure_ai_search",
                index_name=self.index_name,
                search_mode="hybrid",
            ),
            sources_queried=["azure_ai_search"],
        )

    async def _execute_query(
        self,
        spec: QuerySpec,
        request: AgentRequest
    ) -> List[RetrievedChunk]:
        """Execute a single query against Azure AI Search.
        
        Uses asyncio.to_thread() to run the synchronous SearchClient
        in a thread pool, avoiding event loop blocking.
        """
        if not self._client:
            logger.warning("Search client not initialized, returning empty")
            return []

        try:
            from azure.search.documents.models import (
                VectorizableTextQuery,
                QueryType,
            )

            # Get field configuration
            field_config = getattr(self.config, 'field_config', None)
            vector_field = field_config.vector_field if field_config else "contentVector"
            content_field = field_config.content_field if field_config else "content"
            title_field = field_config.title_field if field_config else "title"
            url_field = field_config.url_field if field_config else "url"
            id_field = field_config.id_field if field_config else "id"

            # Build search options
            search_options = {
                "search_text": spec.query_text,
                "top": spec.top_k,
                "include_total_count": True,
            }

            # Add semantic configuration if available
            if self.config.semantic_config:
                search_options["query_type"] = QueryType.SEMANTIC
                search_options["semantic_configuration_name"] = (
                    self.config.semantic_config
                )

            # Add vector query for hybrid search
            if spec.mode in (SearchMode.HYBRID, SearchMode.SEMANTIC):
                vector_query = VectorizableTextQuery(
                    text=spec.query_text,
                    k_nearest_neighbors=spec.top_k,
                    fields=vector_field,  # Use configured field
                )
                search_options["vector_queries"] = [vector_query]

            # Add filters
            if spec.filters:
                filter_parts = []
                for key, value in spec.filters.items():
                    filter_parts.append(f"{key} eq '{value}'")
                search_options["filter"] = " and ".join(filter_parts)

            # Execute search in thread pool to avoid blocking event loop
            def _sync_search():
                return list(self._client.search(**search_options))
            
            results = await asyncio.to_thread(_sync_search)

            # Convert to chunks using field config
            chunks = []
            for result in results:
                chunk = RetrievedChunk(
                    content_id=result.get(id_field, "unknown"),
                    title=result.get(title_field, "Untitled"),
                    url=result.get(url_field),
                    snippet=result.get(content_field, result.get("chunk", ""))[:1000],
                    score=result.get("@search.score", 0) / 10,  # Normalize
                    reranker_score=result.get("@search.reranker_score"),
                    source_system="azure_ai_search",
                    index_name=self.index_name,
                    metadata=result.get("metadata", {}),
                )
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Search query failed: {e}")
            return []
