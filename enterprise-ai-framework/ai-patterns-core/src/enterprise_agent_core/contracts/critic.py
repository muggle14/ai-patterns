"""Critic/Sufficiency contracts for the actor-critic loop.

These contracts define the output of the sufficiency check that
determines whether retrieved content is adequate to answer the query.
"""

from typing import List, Optional
from pydantic import Field

from .base import BaseContract
from .planning import QuerySpec


class SufficiencyResult(BaseContract):
    """Result of the sufficiency check by the Critic.

    Determines whether the retrieved content is sufficient to
    answer the user's query, and if not, what additional
    retrieval is needed.
    """

    # Core decision
    sufficient: bool = Field(
        ...,
        description="Whether retrieved content is sufficient to answer"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the sufficiency decision"
    )

    # Gap analysis (when insufficient)
    missing_aspects: List[str] = Field(
        default_factory=list,
        description="Aspects of the query not covered by retrieval"
    )

    # Next iteration guidance (when insufficient)
    next_query_specs: List[QuerySpec] = Field(
        default_factory=list,
        description="Suggested queries for next retrieval iteration"
    )

    # Reasoning
    reasoning: Optional[str] = Field(
        default=None,
        description="Explanation of the sufficiency decision"
    )

    # Quality indicators
    coverage_estimate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated coverage of query aspects (0-1)"
    )

    relevance_scores: List[float] = Field(
        default_factory=list,
        description="Relevance scores for top chunks"
    )

    # Recommendations
    should_expand_query: bool = Field(
        default=False,
        description="Whether to broaden the search"
    )
    should_change_source: bool = Field(
        default=False,
        description="Whether to try a different data source"
    )
    suggested_source: Optional[str] = Field(
        default=None,
        description="Suggested alternative source if should_change_source is True"
    )
