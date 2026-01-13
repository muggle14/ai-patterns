"""Pytest fixtures for Enterprise Agent Core tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from enterprise_agent_core.contracts.request import AgentRequest, AgentContext, RiskTier
from enterprise_agent_core.contracts.planning import QueryPlan, QuerySpec
from enterprise_agent_core.contracts.retrieval import (
    RetrievalResult,
    RetrievedChunk,
    RetrievalMetrics,
)
from enterprise_agent_core.contracts.critic import SufficiencyResult
from enterprise_agent_core.contracts.response import AgentResponse, Citation
from enterprise_agent_core.interfaces.router import RouteDecision
from enterprise_agent_core.config import AgentConfig, KnowledgeConfig
from enterprise_agent_core.engine.modes import LoopMode, LoopBudget
from enterprise_agent_core.engine.workflow import AgentWorkflowEngine


@pytest.fixture
def sample_request():
    """Create a sample AgentRequest for testing."""
    return AgentRequest(
        request_id="test-123",
        thread_id="thread-456",
        user_query="What is the vacation policy?",
        risk_tier=RiskTier.TIER2,
        metadata={"space": "HR"},
    )


@pytest.fixture
def sample_context():
    """Create a sample AgentContext for testing."""
    return AgentContext(
        correlation_id="corr-789",
        thread_id="thread-456",
    )


@pytest.fixture
def sample_query_plan():
    """Create a sample QueryPlan for testing."""
    return QueryPlan(
        intents=["information_retrieval"],
        subquestions=["What is the vacation policy?"],
        query_specs=[
            QuerySpec(
                query_text="vacation policy",
                top_k=5,
            )
        ],
    )


@pytest.fixture
def sample_retrieval_result():
    """Create a sample RetrievalResult for testing."""
    return RetrievalResult(
        chunks=[
            RetrievedChunk(
                content_id="doc-001",
                title="Vacation Policy",
                url="https://example.com/hr/vacation",
                snippet="Employees are entitled to 15 days of vacation...",
                score=0.92,
                source_system="azure_ai_search",
                metadata={"space": "HR"},
            ),
            RetrievedChunk(
                content_id="doc-002",
                title="Time Off FAQ",
                url="https://example.com/hr/faq",
                snippet="Q: How do I request vacation?",
                score=0.85,
                source_system="azure_ai_search",
                metadata={"space": "HR"},
            ),
        ],
        metrics=RetrievalMetrics(
            latency_ms=150,
            hit_count=2,
            source="azure_ai_search",
        ),
    )


@pytest.fixture
def sample_sufficiency_result():
    """Create a sample SufficiencyResult for testing."""
    return SufficiencyResult(
        sufficient=True,
        confidence=0.9,
        missing_aspects=[],
        next_query_specs=[],
    )


@pytest.fixture
def sample_agent_response():
    """Create a sample AgentResponse for testing."""
    return AgentResponse(
        thread_id="thread-456",
        response_text="Based on the vacation policy...",
        citations=[
            Citation(
                content_id="doc-001",
                url="https://example.com/hr/vacation",
                snippet="Employees are entitled to 15 days...",
                confidence_score=0.92,
            )
        ],
        processing_time_ms=500,
    )


@pytest.fixture
def sample_route_decision():
    """Create a sample RouteDecision for testing."""
    return RouteDecision(
        agent_name="hr",
        loop_mode=LoopMode.PLAN_RAG.value,
        tools_allowed=[],
        confidence=1.0,
        retriever_type="ai_search",
    )


@pytest.fixture
def sample_config():
    """Create a sample AgentConfig for testing."""
    return AgentConfig(
        name="test-agent",
        version="1.0.0",
        model_deployment="gpt-4o",
        loop_mode=LoopMode.PLAN_RAG,
        budget=LoopBudget(max_iterations=2, max_latency_ms=8000),
        knowledge=KnowledgeConfig(
            enabled=True,
            index_name="test-index",
        ),
    )


@pytest.fixture
def mock_router():
    """Create a mock router for testing."""
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteDecision(
        agent_name="test",
        loop_mode=LoopMode.PLAN_RAG.value,
        tools_allowed=[],
    ))
    return router


@pytest.fixture
def mock_planner():
    """Create a mock planner for testing."""
    planner = MagicMock()
    planner.plan = AsyncMock(return_value=QueryPlan(
        intents=["information_retrieval"],
        subquestions=["test query"],
        query_specs=[QuerySpec(query_text="test", top_k=5)],
    ))
    return planner


@pytest.fixture
def mock_retriever(sample_retrieval_result):
    """Create a mock retriever for testing."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=sample_retrieval_result)
    return retriever


@pytest.fixture
def mock_critic():
    """Create a mock critic for testing."""
    critic = MagicMock()
    critic.check = AsyncMock(return_value=SufficiencyResult(
        sufficient=True,
        confidence=0.9,
    ))
    return critic


@pytest.fixture
def mock_synthesizer(sample_agent_response):
    """Create a mock synthesizer for testing."""
    synthesizer = MagicMock()
    synthesizer.write = AsyncMock(return_value=sample_agent_response)
    return synthesizer


@pytest.fixture
def test_engine(mock_router, mock_planner, mock_retriever, mock_critic, mock_synthesizer):
    """Create a test workflow engine with mocked components."""
    return AgentWorkflowEngine(
        router=mock_router,
        planner=mock_planner,
        retriever=mock_retriever,
        critic=mock_critic,
        synthesizer=mock_synthesizer,
        budget=LoopBudget(max_iterations=2, max_latency_ms=8000),
        agent_name="test-agent",
    )
