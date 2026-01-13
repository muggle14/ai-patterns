"""Unit tests for mode switching in the workflow engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise_agent_core.contracts.request import AgentRequest, AgentContext
from enterprise_agent_core.contracts.planning import QueryPlan, QuerySpec
from enterprise_agent_core.contracts.retrieval import (
    RetrievalResult,
    RetrievedChunk,
    RetrievalMetrics,
)
from enterprise_agent_core.contracts.critic import SufficiencyResult
from enterprise_agent_core.contracts.response import AgentResponse
from enterprise_agent_core.interfaces.router import RouteDecision
from enterprise_agent_core.engine.modes import LoopMode, LoopBudget
from enterprise_agent_core.engine.workflow import AgentWorkflowEngine


class TestLoopModes:
    """Tests for LoopMode enum."""

    def test_loop_mode_values(self):
        """Test loop mode enum values."""
        assert LoopMode.FAST_RAG.value == "fast_rag"
        assert LoopMode.PLAN_RAG.value == "plan_rag"
        assert LoopMode.FULL_ACTOR_CRITIC.value == "full_actor_critic"
        assert LoopMode.ACTION_GATED.value == "action_gated"


class TestLoopBudget:
    """Tests for LoopBudget."""

    def test_default_values(self):
        """Test default budget values."""
        budget = LoopBudget()
        assert budget.max_iterations == 2
        assert budget.max_latency_ms == 8000

    def test_custom_values(self):
        """Test custom budget values."""
        budget = LoopBudget(max_iterations=3, max_latency_ms=5000)
        assert budget.max_iterations == 3
        assert budget.max_latency_ms == 5000

    def test_bounds_validation(self):
        """Test budget bounds validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoopBudget(max_iterations=0)

        with pytest.raises(ValidationError):
            LoopBudget(max_iterations=10)


class TestFastRAGMode:
    """Tests for FAST_RAG mode."""

    @pytest.fixture
    def fast_rag_engine(
        self,
        mock_planner,
        mock_retriever,
        mock_critic,
        mock_synthesizer,
    ):
        """Create engine configured for FAST_RAG testing."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="test",
            loop_mode=LoopMode.FAST_RAG.value,
            tools_allowed=[],
        ))

        return AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            budget=LoopBudget(),
            agent_name="test",
        )

    @pytest.mark.asyncio
    async def test_fast_rag_skips_planning(
        self,
        fast_rag_engine,
        sample_request,
        mock_planner,
    ):
        """Test that FAST_RAG mode skips the planning step."""
        await fast_rag_engine.handle(sample_request)

        # Planner should NOT be called in FAST_RAG mode
        mock_planner.plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_fast_rag_skips_critic(
        self,
        fast_rag_engine,
        sample_request,
        mock_critic,
    ):
        """Test that FAST_RAG mode skips the critic step."""
        await fast_rag_engine.handle(sample_request)

        # Critic should NOT be called in FAST_RAG mode
        mock_critic.check.assert_not_called()

    @pytest.mark.asyncio
    async def test_fast_rag_calls_retriever_and_synthesizer(
        self,
        fast_rag_engine,
        sample_request,
        mock_retriever,
        mock_synthesizer,
    ):
        """Test that FAST_RAG calls retriever and synthesizer."""
        await fast_rag_engine.handle(sample_request)

        # Retriever should be called
        mock_retriever.retrieve.assert_called_once()

        # Synthesizer should be called
        mock_synthesizer.write.assert_called_once()


class TestPlanRAGMode:
    """Tests for PLAN_RAG mode."""

    @pytest.fixture
    def plan_rag_engine(
        self,
        mock_planner,
        mock_retriever,
        mock_critic,
        mock_synthesizer,
    ):
        """Create engine configured for PLAN_RAG testing."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="test",
            loop_mode=LoopMode.PLAN_RAG.value,
            tools_allowed=[],
        ))

        return AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            budget=LoopBudget(),
            agent_name="test",
        )

    @pytest.mark.asyncio
    async def test_plan_rag_calls_planner(
        self,
        plan_rag_engine,
        sample_request,
        mock_planner,
    ):
        """Test that PLAN_RAG mode calls the planner."""
        await plan_rag_engine.handle(sample_request)

        # Planner SHOULD be called in PLAN_RAG mode
        mock_planner.plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_rag_skips_critic(
        self,
        plan_rag_engine,
        sample_request,
        mock_critic,
    ):
        """Test that PLAN_RAG mode skips the critic."""
        await plan_rag_engine.handle(sample_request)

        # Critic should NOT be called in PLAN_RAG mode
        mock_critic.check.assert_not_called()


class TestFullActorCriticMode:
    """Tests for FULL_ACTOR_CRITIC mode."""

    @pytest.fixture
    def full_ac_engine(
        self,
        mock_planner,
        mock_retriever,
        mock_synthesizer,
    ):
        """Create engine configured for FULL_ACTOR_CRITIC testing."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="test",
            loop_mode=LoopMode.FULL_ACTOR_CRITIC.value,
            tools_allowed=[],
        ))

        mock_critic = MagicMock()
        mock_critic.check = AsyncMock(return_value=SufficiencyResult(
            sufficient=True,
            confidence=0.9,
        ))

        return AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            budget=LoopBudget(max_iterations=3),
            agent_name="test",
        ), mock_critic

    @pytest.mark.asyncio
    async def test_full_ac_calls_critic(self, full_ac_engine, sample_request):
        """Test that FULL_ACTOR_CRITIC mode calls the critic."""
        engine, mock_critic = full_ac_engine
        await engine.handle(sample_request)

        # Critic SHOULD be called in FULL_ACTOR_CRITIC mode
        mock_critic.check.assert_called()

    @pytest.mark.asyncio
    async def test_full_ac_loops_on_insufficient(
        self,
        mock_planner,
        mock_retriever,
        mock_synthesizer,
        sample_request,
    ):
        """Test that FULL_ACTOR_CRITIC loops when critic returns insufficient."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="test",
            loop_mode=LoopMode.FULL_ACTOR_CRITIC.value,
            tools_allowed=[],
        ))

        # Critic returns insufficient first, then sufficient
        mock_critic = MagicMock()
        mock_critic.check = AsyncMock(side_effect=[
            SufficiencyResult(
                sufficient=False,
                confidence=0.3,
                missing_aspects=["need more info"],
                next_query_specs=[QuerySpec(query_text="expanded query")],
            ),
            SufficiencyResult(
                sufficient=True,
                confidence=0.9,
            ),
        ])

        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            budget=LoopBudget(max_iterations=3),
            agent_name="test",
        )

        response = await engine.handle(sample_request)

        # Critic should be called twice (loop once)
        assert mock_critic.check.call_count == 2

        # Retriever should be called twice (initial + retry)
        assert mock_retriever.retrieve.call_count == 2

    @pytest.mark.asyncio
    async def test_full_ac_respects_max_iterations(
        self,
        mock_planner,
        mock_retriever,
        mock_synthesizer,
        sample_request,
    ):
        """Test that loop respects max_iterations budget."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="test",
            loop_mode=LoopMode.FULL_ACTOR_CRITIC.value,
            tools_allowed=[],
        ))

        # Critic always returns insufficient
        mock_critic = MagicMock()
        mock_critic.check = AsyncMock(return_value=SufficiencyResult(
            sufficient=False,
            confidence=0.2,
            missing_aspects=["still need more"],
        ))

        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            budget=LoopBudget(max_iterations=2),
            agent_name="test",
        )

        await engine.handle(sample_request)

        # Should stop after max_iterations even if not sufficient
        assert mock_critic.check.call_count == 2


class TestResponseMetadata:
    """Tests for response metadata."""

    @pytest.mark.asyncio
    async def test_response_includes_processing_time(
        self,
        test_engine,
        sample_request,
    ):
        """Test that response includes processing time."""
        response = await test_engine.handle(sample_request)
        assert response.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_response_includes_loop_mode(
        self,
        test_engine,
        sample_request,
    ):
        """Test that response includes loop mode."""
        response = await test_engine.handle(sample_request)
        assert response.response_mode in [
            "fast_rag", "plan_rag", "full_actor_critic", "action_gated"
        ]

    @pytest.mark.asyncio
    async def test_response_includes_audit_fields(
        self,
        test_engine,
        sample_request,
    ):
        """Test that response includes audit fields."""
        response = await test_engine.handle(sample_request)
        assert response.audit is not None
        assert response.audit.correlation_id is not None
        assert response.audit.thread_id == sample_request.thread_id
