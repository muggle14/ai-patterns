"""Retrieval module for content retrieval from various sources.

Provides:
- AISearchDirectRetriever: Direct Azure AI Search access
- FoundryIQRetriever: Azure AI Foundry managed KB access
- RetrieverFactory: Dynamic retriever selection
"""

from .ai_search import AISearchDirectRetriever
from .foundry_iq import FoundryIQRetriever
from .factory import RetrieverFactory

__all__ = [
    "AISearchDirectRetriever",
    "FoundryIQRetriever",
    "RetrieverFactory",
]

