"""Integration tests for confluence-bot PLAN_RAG end-to-end flow.

Tests the complete flow from request to response using the
confluence-bot configuration with PLAN_RAG mode.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from enterprise_agent_core.contracts.request import AgentRequest, RiskTier
from enterprise_agent_core.contracts.planning import QueryPlan, QuerySpec
from enterprise_agent_core.contracts.retrieval import RetrievalResult, RetrievedChunk, RetrievalMetrics
from enterprise_agent_core.contracts.critic import SufficiencyResult
from enterprise_agent_core.contracts.response import AgentResponse
from enterprise_agent_core.interfaces.router import RouteDecision
from enterprise_agent_core.engine.modes import LoopMode, LoopBudget
from enterprise_agent_core.engine.workflow import AgentWorkflowEngine
from enterprise_agent_core.config import load_config_from_yaml


@pytest.fixture
def confluence_bot_config():
    """Load confluence-bot configuration."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "../../../../use-cases/confluence-bot/agent.yaml"
    )
    if os.path.exists(config_path):
        return load_config_from_yaml(config_path)
    else:
        from enterprise_agent_core.config import AgentConfig, KnowledgeConfig, WorkflowConfig
        return AgentConfig(
            name="confluence-bot",
            workflow=WorkflowConfig(
                default_mode=LoopMode.PLAN_RAG,
                allowed_modes=[LoopMode.FAST_RAG, LoopMode.PLAN_RAG],
            ),
            knowledge=KnowledgeConfig(
                enabled=True,
                index_name="confluence-content",
            ),
        )


@pytest.fixture
def mock_confluence_retrieval():
    """Create mock retrieval result with Confluence-like content."""
    return RetrievalResult(
        chunks=[
            RetrievedChunk(
                content_id="confluence-page-001",
                title="HR Policy: Vacation Time",
                url="https://confluence.company.com/hr/vacation-policy",
                snippet="All full-time employees are entitled to 15 days of vacation.",
                score=0.95,
                source_system="azure_ai_search",
                index_name="confluence-content",
                metadata={"space": "HR"},
            ),
        ],
        metrics=RetrievalMetrics(
            latency_ms=120,
            hit_count=1,
            source="azure_ai_search",
            index_name="confluence-content",
        ),
    )


class TestConfluenceBotPlanRAG:
    """Integration tests for confluence-bot PLAN_RAG mode."""

    @pytest.mark.asyncio
    async def test_plan_rag_end_to_end(self, confluence_bot_config, mock_confluence_retrieval):
        """Test complete PLAN_RAG flow."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="confluence",
            loop_mode=LoopMode.PLAN_RAG.value,
            tools_allowed=[],
            confidence=0.9,
        ))

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=QueryPlan(
            intents=["information_retrieval"],
            query_specs=[QuerySpec(query_text="vacation policy", top_k=5)],
        ))

        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value=mock_confluence_retrieval)

        mock_critic = MagicMock()
        mock_critic.check = AsyncMock(return_value=SufficiencyResult(
            sufficient=True,
            confidence=0.92,
            missing_aspects=[],
        ))

        # Create mock response
        mock_response = MagicMock()
        mock_response.response = "Based on the HR vacation policy..."
        mock_response.response_text = mock_response.response
        mock_response.response_mode = LoopMode.PLAN_RAG.value
        mock_response.citations = [{"content_id": "confluence-page-001"}]
        mock_response.audit = MagicMock()
        mock_response.audit.agent_name = "confluence-bot"
        mock_response.audit.data_sources_used = ["azure_ai_search"]
        
        mock_synthesizer = MagicMock()
        mock_synthesizer.write = AsyncMock(return_value=mock_response)

        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            agent_name="confluence-bot",
            default_loop_mode=LoopMode.PLAN_RAG,
        )

        request = AgentRequest(
            request_id="confluence-int-001",
            thread_id="thread-confluence",
            user_query="What is the vacation policy?",
            risk_tier=RiskTier.TIER1,
        )

        response = await engine.handle(request)

        # Verify
        mock_router.route.assert_called_once()
        mock_planner.plan.assert_called_once()
        mock_retriever.retrieve.assert_called_once()
        assert response is not None
        assert response.response_mode == LoopMode.PLAN_RAG.value

    @pytest.mark.asyncio
    async def test_no_tools_for_readonly_bot(self, confluence_bot_config):
        """Confluence-bot should never execute tools (read-only)."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=RouteDecision(
            agent_name="confluence",
            loop_mode=LoopMode.PLAN_RAG.value,
            tools_allowed=[],
            confidence=0.9,
        ))

        mock_tool_executor = MagicMock()
        mock_tool_executor.execute = AsyncMock()

        mock_response = MagicMock()
        mock_response.response_mode = LoopMode.PLAN_RAG.value
        mock_response.response = "Answer"
        mock_response.response_text = "Answer"

        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["info"], query_specs=[QuerySpec(query_text="test")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=RetrievalResult(
                chunks=[], metrics=RetrievalMetrics(latency_ms=50, hit_count=0, source="test")
            ))),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(
                sufficient=True, confidence=0.9, missing_aspects=[]
            ))),
            synthesizer=MagicMock(write=AsyncMock(return_value=mock_response)),
            tool_executor=mock_tool_executor,
        )

        request = AgentRequest(
            request_id="test",
            thread_id="test",
            user_query="What is policy?",
            risk_tier=RiskTier.TIER1,
        )

        await engine.handle(request)

        # Tool executor should never be called for PLAN_RAG
        mock_tool_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_citations_included_in_response(self, mock_confluence_retrieval):
        """Response should include proper citations."""
        mock_response = MagicMock()
        mock_response.response = "Answer with citation"
        mock_response.response_text = "Answer with citation"
        mock_response.citations = [{"content_id": "confluence-page-001"}]
        mock_response.response_mode = LoopMode.PLAN_RAG.value
        
        mock_synthesizer = MagicMock()
        mock_synthesizer.write = AsyncMock(return_value=mock_response)

        engine = AgentWorkflowEngine(
            router=MagicMock(route=AsyncMock(return_value=RouteDecision(
                agent_name="confluence", loop_mode=LoopMode.PLAN_RAG.value
            ))),
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["info"], query_specs=[QuerySpec(query_text="test")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=mock_confluence_retrieval)),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(
                sufficient=True, confidence=0.9, missing_aspects=[]
            ))),
            synthesizer=mock_synthesizer,
        )

        request = AgentRequest(
            request_id="test", thread_id="test", user_query="vacation policy"
        )

        response = await engine.handle(request)

        assert response.citations is not None
        assert len(response.citations) > 0
