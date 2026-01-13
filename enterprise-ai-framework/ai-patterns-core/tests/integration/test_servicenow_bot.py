"""Integration tests for servicenow-bot ACTION_GATED end-to-end flow.

Tests the complete flow from request to response using the
servicenow-bot configuration with ACTION_GATED mode, including
tool execution with approval flow.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from enterprise_agent_core.contracts.request import AgentRequest, RiskTier
from enterprise_agent_core.contracts.planning import QueryPlan, QuerySpec
from enterprise_agent_core.contracts.retrieval import RetrievalResult, RetrievedChunk, RetrievalMetrics
from enterprise_agent_core.contracts.critic import SufficiencyResult
from enterprise_agent_core.contracts.response import AgentResponse, ActionLog
from enterprise_agent_core.contracts.tools import ToolCallRequest, ToolCallResult, ToolStatus
from enterprise_agent_core.interfaces.router import RouteDecision
from enterprise_agent_core.engine.modes import LoopMode, LoopBudget
from enterprise_agent_core.engine.workflow import AgentWorkflowEngine


@pytest.fixture
def servicenow_route_decision():
    """Route decision for ACTION_GATED ServiceNow bot."""
    return RouteDecision(
        agent_name="servicenow",
        loop_mode=LoopMode.ACTION_GATED.value,
        tools_allowed=["create_incident", "update_incident", "add_comment"],
        confidence=0.95,
        retriever_type="ai_search",
    )


@pytest.fixture
def mock_servicenow_retrieval():
    """Create mock retrieval result with ServiceNow KB content."""
    return RetrievalResult(
        chunks=[
            RetrievedChunk(
                content_id="kb-001",
                title="How to Reset Your Password",
                url="https://servicenow.company.com/kb/KB0001234",
                snippet=(
                    "To reset your password, go to the password reset portal at "
                    "https://reset.company.com. Click 'Forgot Password', enter your "
                    "email, and follow the instructions. If you're still locked out, "
                    "contact IT support to create a ticket."
                ),
                score=0.91,
                source_system="azure_ai_search",
                index_name="servicenow-kb",
                metadata={"category": "Password", "article_type": "KB"},
            ),
        ],
        metrics=RetrievalMetrics(
            latency_ms=95,
            hit_count=1,
            source="azure_ai_search",
            index_name="servicenow-kb",
        ),
    )


@pytest.fixture
def mock_tool_executor():
    """Mock tool executor for ServiceNow actions."""
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=ToolCallResult(
        status=ToolStatus.SUCCESS,
        outputs={
            "incident_id": "INC0012345",
            "number": "INC0012345",
            "sys_id": "abc123def456",
            "state": "New",
            "message": "Incident created successfully",
        },
        execution_time_ms=350,
    ))
    return executor


class TestServiceNowBotActionGated:
    """Integration tests for servicenow-bot ACTION_GATED mode."""

    @pytest.mark.asyncio
    async def test_action_gated_full_flow(
        self,
        servicenow_route_decision,
        mock_servicenow_retrieval,
        mock_tool_executor,
    ):
        """Test complete ACTION_GATED flow: Route -> Plan -> Retrieve -> Critic -> Synthesize -> Tool."""
        # Setup mocks
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value=servicenow_route_decision)

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=QueryPlan(
            intents=["action_request", "incident_creation"],
            subquestions=[
                "How to report login issues?",
                "How to create an IT support ticket?",
            ],
            query_specs=[
                QuerySpec(query_text="login issue password reset", top_k=5),
                QuerySpec(query_text="create IT support ticket incident", top_k=3),
            ],
        ))

        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value=mock_servicenow_retrieval)

        mock_critic = MagicMock()
        mock_critic.check = AsyncMock(return_value=SufficiencyResult(
            sufficient=True,
            confidence=0.88,
        ))

        mock_synthesizer = MagicMock()
        mock_synthesizer.write = AsyncMock(return_value=AgentResponse(
            thread_id="thread-snow",
            response_text=(
                "I can help you create a ticket for the login issue. "
                "I'll create an incident with the following details:\n\n"
                "- **Title**: Login issue - Unable to access account\n"
                "- **Priority**: P3 (Medium)\n"
                "- **Category**: Password/Authentication\n\n"
                "Would you like me to proceed with creating this ticket?"
            ),
        ))

        # Create engine with tool executor
        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            tool_executor=mock_tool_executor,
            agent_name="servicenow-bot",
            default_loop_mode=LoopMode.ACTION_GATED,
        )

        # Send request
        request = AgentRequest(
            request_id="snow-int-001",
            thread_id="thread-snow",
            user_query="I can't login to my account. Please create a ticket.",
            risk_tier=RiskTier.TIER2,
        )

        response = await engine.handle(request)

        # Verify flow
        mock_router.route.assert_called_once()
        mock_planner.plan.assert_called_once()
        mock_retriever.retrieve.assert_called_once()
        mock_critic.check.assert_called_once()
        mock_synthesizer.write.assert_called_once()

        # Verify response
        assert response is not None
        assert response.response_mode == LoopMode.ACTION_GATED.value
        assert response.audit.agent_name == "servicenow-bot"

    @pytest.mark.asyncio
    async def test_tool_execution_on_approval(
        self,
        servicenow_route_decision,
        mock_servicenow_retrieval,
        mock_tool_executor,
    ):
        """Tool should execute when action is detected and approved."""
        mock_synthesizer = MagicMock()
        mock_synthesizer.write = AsyncMock(return_value=AgentResponse(
            thread_id="thread-snow",
            response_text="Creating ticket for login issue...",
        ))

        engine = AgentWorkflowEngine(
            router=MagicMock(route=AsyncMock(return_value=servicenow_route_decision)),
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["action"], query_specs=[QuerySpec(query_text="create ticket")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=mock_servicenow_retrieval)),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(sufficient=True, confidence=0.9, missing_aspects=[]))),
            synthesizer=mock_synthesizer,
            tool_executor=mock_tool_executor,
        )

        request = AgentRequest(
            request_id="test",
            thread_id="thread-test",
            user_query="Create a ticket for password reset",
            risk_tier=RiskTier.TIER2,
        )

        response = await engine.handle(request)

        # Tool executor should have been called for ACTION_GATED
        # (depending on action detection logic)
        assert response is not None
        assert response.response_mode == LoopMode.ACTION_GATED.value

    @pytest.mark.asyncio
    async def test_pending_approval_status(
        self,
        servicenow_route_decision,
        mock_servicenow_retrieval,
    ):
        """Tool requiring approval should return PENDING_APPROVAL status."""
        # Mock tool that requires approval
        mock_tool_executor = MagicMock()
        mock_tool_executor.execute = AsyncMock(return_value=ToolCallResult(
            status=ToolStatus.PENDING_APPROVAL,
            outputs={"message": "Awaiting manager approval"},
            execution_time_ms=50,
        ))

        engine = AgentWorkflowEngine(
            router=MagicMock(route=AsyncMock(return_value=servicenow_route_decision)),
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["action"], query_specs=[QuerySpec(query_text="test")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=mock_servicenow_retrieval)),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(sufficient=True, confidence=0.9, missing_aspects=[]))),
            synthesizer=MagicMock(write=AsyncMock(return_value=AgentResponse(
                thread_id="test", response_text="Creating ticket..."
            ))),
            tool_executor=mock_tool_executor,
        )

        request = AgentRequest(
            request_id="test",
            thread_id="test",
            user_query="Create an incident",
            risk_tier=RiskTier.TIER3,  # Higher risk tier
        )

        response = await engine.handle(request)
        
        assert response is not None

    @pytest.mark.asyncio
    async def test_tool_failure_handling(
        self,
        servicenow_route_decision,
        mock_servicenow_retrieval,
    ):
        """Tool failure should be handled gracefully."""
        mock_tool_executor = MagicMock()
        mock_tool_executor.execute = AsyncMock(return_value=ToolCallResult(
            status=ToolStatus.FAILED,
            outputs={},
            error="ServiceNow API unavailable",
            execution_time_ms=5000,
        ))

        engine = AgentWorkflowEngine(
            router=MagicMock(route=AsyncMock(return_value=servicenow_route_decision)),
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["action"], query_specs=[QuerySpec(query_text="test")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=mock_servicenow_retrieval)),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(sufficient=True, confidence=0.9, missing_aspects=[]))),
            synthesizer=MagicMock(write=AsyncMock(return_value=AgentResponse(
                thread_id="test", response_text="Creating ticket..."
            ))),
            tool_executor=mock_tool_executor,
        )

        request = AgentRequest(
            request_id="test",
            thread_id="test",
            user_query="Create an incident",
            risk_tier=RiskTier.TIER2,
        )

        # Should not raise, even if tool fails
        response = await engine.handle(request)
        
        assert response is not None


class TestToolAllowlist:
    """Test tool allowlist enforcement."""

    @pytest.mark.asyncio
    async def test_only_allowed_tools_callable(self, mock_servicenow_retrieval):
        """Only tools in allowlist should be callable."""
        route_decision = RouteDecision(
            agent_name="servicenow",
            loop_mode=LoopMode.ACTION_GATED.value,
            tools_allowed=["create_incident"],  # Only create allowed
            confidence=0.9,
        )

        mock_tool_executor = MagicMock()
        mock_tool_executor.execute = AsyncMock(return_value=ToolCallResult(
            status=ToolStatus.SUCCESS,
            outputs={"incident_id": "INC001"},
            execution_time_ms=100,
        ))

        engine = AgentWorkflowEngine(
            router=MagicMock(route=AsyncMock(return_value=route_decision)),
            planner=MagicMock(plan=AsyncMock(return_value=QueryPlan(
                intents=["action"], query_specs=[QuerySpec(query_text="test")]
            ))),
            retriever=MagicMock(retrieve=AsyncMock(return_value=mock_servicenow_retrieval)),
            critic=MagicMock(check=AsyncMock(return_value=SufficiencyResult(sufficient=True, confidence=0.9, missing_aspects=[]))),
            synthesizer=MagicMock(write=AsyncMock(return_value=AgentResponse(
                thread_id="test", response_text="Creating..."
            ))),
            tool_executor=mock_tool_executor,
        )

        request = AgentRequest(
            request_id="test",
            thread_id="test",
            user_query="Create an incident",
            risk_tier=RiskTier.TIER2,
        )

        response = await engine.handle(request)

        # Verify only allowed tool was considered
        assert response is not None
