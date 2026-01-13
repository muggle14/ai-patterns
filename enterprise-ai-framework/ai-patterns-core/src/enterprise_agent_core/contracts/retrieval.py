"""Retrieval contracts for search results.

These contracts define the structure of retrieved content from
Azure AI Search, Foundry IQ Knowledge Base, and other sources.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract


class RetrievedChunk(BaseContract):
    """A single retrieved content chunk.

    Represents a search result from Azure AI Search, Foundry IQ KB,
    or any other retrieval source. Designed for citation generation.
    """

    # Identification
    content_id: str = Field(..., description="Unique content identifier")
    title: str = Field(..., description="Document or chunk title")
    url: Optional[str] = Field(default=None, description="Source URL for citation")

    # Content
    snippet: str = Field(..., description="Retrieved text content")

    # Scoring
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (normalized 0-1)"
    )
    reranker_score: Optional[float] = Field(
        default=None,
        description="Semantic reranker score if applied"
    )

    # Source tracking
    source_system: str = Field(
        ...,
        description="Source system (azure_ai_search, foundry_iq, confluence, sharepoint)"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Azure AI Search index name"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (doc_type, space, version, etc.)"
    )

    # Access control (placeholder for future per-user trimming)
    access_groups: List[str] = Field(
        default_factory=list,
        description="Groups with access to this content"
    )


class RetrievalMetrics(BaseContract):
    """Metrics from the retrieval operation.

    Used for observability and debugging retrieval quality.
    """

    latency_ms: float = Field(..., description="Retrieval latency in milliseconds")
    hit_count: int = Field(..., description="Number of results returned")
    total_available: Optional[int] = Field(
        default=None,
        description="Total matching documents (if known)"
    )

    # Source info
    source: str = Field(..., description="Retrieval source used")
    index_name: Optional[str] = Field(default=None, description="Index queried")

    # Query details
    applied_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters that were applied"
    )
    search_mode: Optional[str] = Field(
        default=None,
        description="Search mode used (semantic, keyword, hybrid)"
    )

    # Quality hints
    coverage_score: Optional[float] = Field(
        default=None,
        description="Estimated coverage of the query (0-1)"
    )


class RetrievalResult(BaseContract):
    """Complete retrieval result from one or more sources.

    Aggregates chunks from potentially multiple Azure AI Search indexes
    or Foundry IQ Knowledge Bases.
    """

    chunks: List[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved content chunks"
    )

    metrics: RetrievalMetrics = Field(
        ...,
        description="Retrieval performance metrics"
    )

    # Multi-source tracking
    sources_queried: List[str] = Field(
        default_factory=list,
        description="All sources that were queried"
    )

    # For comparison use cases
    comparison_chunks: Optional[Dict[str, List[RetrievedChunk]]] = Field(
        default=None,
        description="Paired chunks for comparison: {left: [...], right: [...]}"
    )
