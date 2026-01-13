"""Tests for RetrieverFactory selection logic.

Tests dynamic retriever selection based on retriever_type,
caching behavior, and fallback handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from enterprise_agent_core.retrieval.factory import RetrieverFactory
from enterprise_agent_core.retrieval.ai_search import AISearchDirectRetriever
from enterprise_agent_core.config import KnowledgeConfig, AgentConfig


class TestRetrieverFactorySelection:
    """Test retriever selection logic."""

    def test_factory_initialization(self):
        """Factory should initialize with config."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        assert factory.config == config
        assert factory._instances == {}

    def test_get_ai_search_retriever(self):
        """Should return AISearchDirectRetriever for 'ai_search' type."""
        config = AgentConfig(
            name="test",
            knowledge=KnowledgeConfig(
                index_name="test-index",
            ),
        )
        factory = RetrieverFactory(config)
        
        retriever = factory.get_retriever("ai_search")
        
        assert isinstance(retriever, AISearchDirectRetriever)
        assert retriever.index_name == "test-index"

    def test_retriever_caching(self):
        """Same retriever_type should return cached instance."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        retriever1 = factory.get_retriever("ai_search")
        retriever2 = factory.get_retriever("ai_search")
        
        # Should be the same instance
        assert retriever1 is retriever2

    def test_different_types_not_cached_together(self):
        """Different retriever types should have separate cache entries."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        ai_search = factory.get_retriever("ai_search")
        # Foundry IQ will be a different type
        foundry = factory.get_retriever("foundry_iq")
        
        assert ai_search is not foundry

    def test_unsupported_type_raises_error(self):
        """Unsupported retriever type should raise ValueError."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        with pytest.raises(ValueError) as exc:
            factory.get_retriever("unsupported_type")
        
        assert "unsupported_type" in str(exc.value)

    def test_default_retriever(self):
        """get_default_retriever should return the default retriever type."""
        config = AgentConfig(
            name="test",
            knowledge=KnowledgeConfig(mode="ai_search"),
        )
        factory = RetrieverFactory(config)
        
        default = factory.get_default_retriever()
        
        assert isinstance(default, AISearchDirectRetriever)


class TestRetrieverRegistration:
    """Test custom retriever registration."""

    def test_register_custom_retriever(self):
        """Should be able to register custom retriever factory."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        # Register a mock class
        MockRetriever = MagicMock
        RetrieverFactory.register("custom", MockRetriever)
        
        # Verify it was registered
        assert "custom" in RetrieverFactory._registry

    def test_supports_method(self):
        """Should correctly check if retriever type is supported."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        assert factory.supports("ai_search") is True
        assert factory.supports("foundry_iq") is True
        assert factory.supports("confluence") is True  # Falls back
        assert factory.supports("nonexistent") is False


class TestRetrieverWithRouteDecision:
    """Test retriever selection based on RouteDecision."""

    def test_get_from_route_decision(self):
        """Should select retriever based on RouteDecision.retriever_type."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        # Mock RouteDecision
        route_decision = MagicMock()
        route_decision.retriever_type = "ai_search"
        
        retriever = factory.get_retriever(route_decision.retriever_type)
        
        assert isinstance(retriever, AISearchDirectRetriever)

    def test_fallback_to_default_on_none(self):
        """If retriever_type is None, should return default."""
        config = AgentConfig(name="test")
        factory = RetrieverFactory(config)
        
        route_decision = MagicMock()
        route_decision.retriever_type = None
        
        # Pass None - factory should use config default
        retriever = factory.get_retriever(route_decision.retriever_type)
        
        assert isinstance(retriever, AISearchDirectRetriever)

