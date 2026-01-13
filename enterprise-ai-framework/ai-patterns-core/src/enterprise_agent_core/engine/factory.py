"""Engine wiring factory.

Creates fully-wired engine instances from configuration.
Supports config-driven component selection without hardcoded agent IDs.
"""

import os
import logging
from typing import Dict, Optional

from azure.identity import DefaultAzureCredential

from ..config import AgentConfig, KnowledgeConfig, RetrieverMode, LogicAppConfig
from ..interfaces import IRetriever
from ..retrieval.ai_search import AISearchDirectRetriever
from ..retrieval.foundry_iq import FoundryIQRetriever
from .routers.classic import ClassicRouter
from .routers.maf_preview import MAFRouter

logger = logging.getLogger(__name__)


class RetrieverFactory:
    """Factory for creating retrievers based on route decision.

    Caches retriever instances by type and index name to avoid
    recreating clients on every request.
    """

    def __init__(self, config: AgentConfig):
        """Initialize the retriever factory.

        Args:
            config: Agent configuration with knowledge settings
        """
        self.config = config
        self._cache: Dict[str, IRetriever] = {}

    def get_retriever(
        self,
        retriever_type: Optional[str] = None,
        index_name: Optional[str] = None,
    ) -> IRetriever:
        """Get or create retriever for the specified type.

        Args:
            retriever_type: Type of retriever (ai_search, foundry_iq)
                           Defaults to config.knowledge.mode
            index_name: Optional index name override

        Returns:
            Configured retriever instance
        """
        # Default to config mode
        if not retriever_type:
            retriever_type = self.config.knowledge.mode.value

        # Build cache key
        cache_key = f"{retriever_type}:{index_name or 'default'}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Create new retriever
        retriever = self._create_retriever(retriever_type, index_name)
        self._cache[cache_key] = retriever

        logger.info(f"Created retriever: {retriever_type} (index: {index_name})")
        return retriever

    def _create_retriever(
        self,
        retriever_type: str,
        index_name: Optional[str] = None,
    ) -> IRetriever:
        """Create a new retriever instance.

        Args:
            retriever_type: Type of retriever to create
            index_name: Optional index name override

        Returns:
            New retriever instance
        """
        if retriever_type == RetrieverMode.FOUNDRY_IQ.value:
            return FoundryIQRetriever(
                config=self.config.knowledge,
                kb_name=index_name or self.config.knowledge.kb_name,
                project_endpoint=self.config.project_endpoint,
            )

        # Default to AI Search
        knowledge_config = self.config.knowledge

        # Override index name if provided
        if index_name:
            knowledge_config = KnowledgeConfig(
                enabled=knowledge_config.enabled,
                mode=knowledge_config.mode,
                search_endpoint=knowledge_config.search_endpoint,
                index_name=index_name,
                semantic_config=knowledge_config.semantic_config,
                kb_name=knowledge_config.kb_name,
                default_top_k=knowledge_config.default_top_k,
                use_semantic_reranking=knowledge_config.use_semantic_reranking,
            )

        # Determine mock mode from environment
        mock_mode = os.environ.get("RETRIEVAL_MOCK_MODE", "true").lower() == "true"
        if knowledge_config.search_endpoint:
            mock_mode = False

        return AISearchDirectRetriever(
            config=knowledge_config,
            mock_mode=mock_mode,
        )


class WiringFactory:
    """Factory for creating wired engine components from config.

    Replaces the old factory with config-driven component selection.
    Uses project_endpoint as primary connection method.
    """

    @staticmethod
    def create_retriever_factory(config: AgentConfig) -> RetrieverFactory:
        """Create a retriever factory for the given config.

        Args:
            config: Agent configuration

        Returns:
            RetrieverFactory instance
        """
        return RetrieverFactory(config)

    @staticmethod
    def create_router(
        config: AgentConfig,
        agent_map: Optional[Dict[str, object]] = None,
    ):
        """Create router based on config.

        Args:
            config: Agent configuration
            agent_map: Optional map of agent names to adapters

        Returns:
            Router instance (ClassicRouter or MAFRouter)
        """
        # Check feature flag for MAF
        use_maf = config.enable_maf_router or os.environ.get("ROUTER_MODE") == "maf"

        if use_maf:
            logger.warning("MAFRouter enabled - PREVIEW feature")
            return MAFRouter(
                config=config,
                default_loop_mode=config.loop_mode,
                agent_map=agent_map or {},
            )

        return ClassicRouter(
            config=config,
            default_loop_mode=config.loop_mode,
            agent_map=agent_map or {},
        )

    @staticmethod
    def create_tool_executor(config: AgentConfig):
        """Create tool executor from config.

        Args:
            config: Agent configuration with logic_apps settings

        Returns:
            BasicToolExecutor instance
        """
        from ..tools.executor import BasicToolExecutor

        # Build logic apps map
        logic_apps_map: Dict[str, LogicAppConfig] = {}
        for la in config.logic_apps:
            logic_apps_map[la.name] = la

        return BasicToolExecutor(
            logic_apps=logic_apps_map,
            default_timeout_ms=30000,
            max_retries=2,
        )

    @staticmethod
    def create_ai_client(config: AgentConfig):
        """Create Azure AI Project client from config.

        Prefers project_endpoint over project_connection_string.

        Args:
            config: Agent configuration

        Returns:
            AIProjectClient instance or None if not configured
        """
        try:
            from azure.ai.projects import AIProjectClient
        except ImportError:
            logger.warning("azure-ai-projects not installed")
            return None

        credential = DefaultAzureCredential()

        if config.project_endpoint:
            return AIProjectClient(
                endpoint=config.project_endpoint,
                credential=credential,
            )

        if config.project_connection_string:
            import warnings
            warnings.warn(
                "project_connection_string is deprecated. "
                "Use project_endpoint instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return AIProjectClient.from_connection_string(
                config.project_connection_string,
                credential=credential,
            )

        logger.warning("No project_endpoint or project_connection_string configured")
        return None
