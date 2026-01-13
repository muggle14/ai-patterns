"""Planning contracts for query decomposition.

These contracts define how user queries are decomposed into structured
search specifications for Azure AI Search and Foundry IQ Knowledge Base.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract


class SearchMode(str, Enum):
    """Search mode for retrieval."""
    SEMANTIC = "semantic"      # Semantic/vector search only
    KEYWORD = "keyword"        # Keyword/BM25 search only
    HYBRID = "hybrid"          # Combined semantic + keyword (recommended)


class QuerySpec(BaseContract):
    """Specification for a single search query.

    This maps directly to Azure AI Search query parameters,
    supporting both direct AI Search and Foundry IQ KB queries.
    """

    query_text: str = Field(..., description="The search query text")

    # Source preference
    source_preference: Optional[str] = Field(
        default=None,
        description="Preferred source system (confluence, sharepoint, foundry_iq)"
    )

    # Azure AI Search parameters
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="OData filter expressions for Azure AI Search"
    )
    facets: List[str] = Field(
        default_factory=list,
        description="Facet fields to aggregate (e.g., doc_type, space)"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of results to retrieve"
    )

    # Search configuration
    rerank: bool = Field(
        default=False,
        description="Whether to apply semantic reranking"
    )
    mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="Search mode (semantic, keyword, or hybrid)"
    )

    # Vector search configuration (for Azure AI Search)
    vector_fields: List[str] = Field(
        default_factory=list,
        description="Vector fields to search (uses server-side vectorization)"
    )

    # Semantic configuration name (Azure AI Search)
    semantic_config: Optional[str] = Field(
        default=None,
        description="Semantic configuration name for Azure AI Search"
    )


class QueryPlan(BaseContract):
    """Query decomposition plan from the Planner.

    Breaks down a user query into intents, sub-questions, and
    structured query specifications for retrieval.
    """

    # Intent classification
    intents: List[str] = Field(
        default_factory=list,
        description="Detected intents (information_retrieval, action_request, comparison)"
    )

    # Query decomposition
    subquestions: List[str] = Field(
        default_factory=list,
        description="Decomposed sub-questions for complex queries"
    )

    # Structured query specifications
    query_specs: List[QuerySpec] = Field(
        default_factory=list,
        description="Query specifications for retrieval"
    )

    # Planning metadata
    requires_multi_source: bool = Field(
        default=False,
        description="Whether multiple data sources are needed"
    )
    requires_comparison: bool = Field(
        default=False,
        description="Whether document comparison is needed"
    )

    # For document comparison use cases (e.g., contract v1 vs v2)
    comparison_spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Comparison specification: {left_doc_id, right_doc_id, sections}"
    )
