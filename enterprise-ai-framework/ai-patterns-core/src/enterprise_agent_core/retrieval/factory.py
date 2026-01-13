"""Retriever Factory for dynamic retriever selection.

Provides dynamic retriever selection based on RouteDecision.retriever_type
and agent configuration. This enables the engine to select different
retrieval strategies per request.

Supported retriever types:
- ai_search: Direct Azure AI Search retrieval
- foundry_iq: Azure AI Foundry managed Knowledge Base (KB)
- confluence: Confluence API retrieval (future)
- sharepoint: SharePoint API retrieval (future)
"""

import logging
from typing import Dict, Optional, Type

from ..config import AgentConfig, KnowledgeConfig, RetrieverMode
from ..interfaces.retriever import IRetriever
from .ai_search import AISearchDirectRetriever
from .foundry_iq import FoundryIQRetriever

logger = logging.getLogger(__name__)


class RetrieverFactory:
    """Factory for creating and caching retriever instances.
    
    Provides:
    - Dynamic retriever selection based on type string
    - Instance caching for efficiency
    - Configuration-aware initialization
    - Fallback handling for unsupported types
    """

    # Registry of retriever types to their implementations
    _registry: Dict[str, Type[IRetriever]] = {
        "ai_search": AISearchDirectRetriever,
        "foundry_iq": FoundryIQRetriever,
    }

    def __init__(self, config: AgentConfig):
        """Initialize the factory with agent config.
        
        Args:
            config: Agent configuration containing knowledge settings
        """
        self.config = config
        self.knowledge_config = config.knowledge
        self._instances: Dict[str, IRetriever] = {}

    def get_retriever(
        self,
        retriever_type: Optional[str] = None,
        index_name: Optional[str] = None,
    ) -> IRetriever:
        """Get or create a retriever instance.
        
        Args:
            retriever_type: Type of retriever ("ai_search", "foundry_iq", etc.)
                           If None, uses config default.
            index_name: Optional override for index name
            
        Returns:
            IRetriever instance for the requested type
            
        Raises:
            ValueError: If retriever type is not supported
        """
        # Default to config mode
        if retriever_type is None:
            retriever_type = self.knowledge_config.mode.value

        # Normalize type string
        retriever_type = retriever_type.lower().replace("-", "_")

        # Check cache - keyed by type + index for AI Search
        cache_key = f"{retriever_type}:{index_name or 'default'}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        # Create new instance
        retriever = self._create_retriever(retriever_type, index_name)
        self._instances[cache_key] = retriever

        logger.info(
            f"Created retriever: type={retriever_type}, "
            f"index={index_name or self.knowledge_config.index_name}, "
            f"mock_mode={self.knowledge_config.mock_mode}"
        )

        return retriever

    def _create_retriever(
        self,
        retriever_type: str,
        index_name: Optional[str] = None,
    ) -> IRetriever:
        """Create a new retriever instance.
        
        Args:
            retriever_type: Type of retriever
            index_name: Optional index name override
            
        Returns:
            New IRetriever instance
        """
        if retriever_type == "ai_search":
            return AISearchDirectRetriever(
                config=self.knowledge_config,
                index_name=index_name or self.knowledge_config.index_name,
                mock_mode=self.knowledge_config.mock_mode,
            )

        elif retriever_type == "foundry_iq":
            return FoundryIQRetriever(
                config=self.knowledge_config,
                kb_name=self.knowledge_config.kb_name,
            )

        elif retriever_type in ("confluence", "sharepoint"):
            # Future implementations - fall back to AI Search for now
            logger.warning(
                f"Retriever type '{retriever_type}' not fully implemented, "
                "falling back to AI Search"
            )
            return AISearchDirectRetriever(
                config=self.knowledge_config,
                mock_mode=self.knowledge_config.mock_mode,
            )

        else:
            raise ValueError(
                f"Unsupported retriever type: {retriever_type}. "
                f"Supported: {list(self._registry.keys())}"
            )

    def get_default_retriever(self) -> IRetriever:
        """Get the default retriever based on configuration.
        
        Returns:
            Default IRetriever instance
        """
        return self.get_retriever()

    @classmethod
    def register(cls, type_name: str, retriever_class: Type[IRetriever]) -> None:
        """Register a new retriever type.
        
        Args:
            type_name: The type identifier (e.g., "custom_api")
            retriever_class: The IRetriever implementation class
        """
        cls._registry[type_name] = retriever_class
        logger.info(f"Registered retriever type: {type_name}")

    def supports(self, retriever_type: str) -> bool:
        """Check if a retriever type is supported.
        
        Args:
            retriever_type: Type to check
            
        Returns:
            True if the type is supported
        """
        normalized = retriever_type.lower().replace("-", "_")
        return normalized in self._registry or normalized in ("confluence", "sharepoint")
