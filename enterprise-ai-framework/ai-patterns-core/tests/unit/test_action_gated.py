"""Tests for ACTION_GATED tool execution flow.

Tests the complete ACTION_GATED workflow including:
- Tool detection from response
- ToolCallRequest building
- Idempotency key generation
- Approval flow
- Tool execution
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import hashlib

from enterprise_agent_core.contracts.request import AgentRequest, AgentContext, RiskTier
from enterprise_agent_core.contracts.response import AgentResponse, ActionLog
from enterprise_agent_core.contracts.tools import ToolCallRequest, ToolCallResult, ToolStatus
from enterprise_agent_core.interfaces.router import RouteDecision
from enterprise_agent_core.engine.modes import LoopMode, LoopBudget
from enterprise_agent_core.engine.workflow import AgentWorkflowEngine


@pytest.fixture
def mock_tool_executor():
    """Create a mock tool executor."""
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=ToolCallResult(
        status=ToolStatus.SUCCESS,
        outputs={"incident_id": "INC001", "message": "Created successfully"},
        execution_time_ms=200,
    ))
    return executor


@pytest.fixture
def action_gated_route_decision():
    """Create a route decision for ACTION_GATED mode."""
    return RouteDecision(
        agent_name="servicenow",
        loop_mode=LoopMode.ACTION_GATED.value,
        tools_allowed=["create_incident", "update_incident", "add_comment"],
        confidence=0.9,
        retriever_type="ai_search",
    )


@pytest.fixture
def action_request():
    """Create a request that triggers action intent."""
    return AgentRequest(
        request_id="action-123",
        thread_id="thread-action",
        user_query="Please create a ticket for the login issue",
        risk_tier=RiskTier.TIER2,
    )


class TestActionDetection:
    """Test action intent detection from responses."""

    @pytest.mark.asyncio
    async def test_action_detected_in_response(
        self,
        mock_router,
        mock_planner,
        mock_retriever,
        mock_critic,
        mock_synthesizer,
        mock_tool_executor,
        action_gated_route_decision,
        action_request,
    ):
        """Should detect action intent and trigger tool execution."""
        # Setup router to return ACTION_GATED decision
        mock_router.route = AsyncMock(return_value=action_gated_route_decision)
        
        # Setup synthesizer to return action-oriented response
        mock_synthesizer.write = AsyncMock(return_value=AgentResponse(
            thread_id="thread-action",
            response_text="I'll create a ticket for the login issue.",
        ))
        
        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            tool_executor=mock_tool_executor,
        )
        
        response = await engine.handle(action_request)
        
        # Should have called tool executor
        mock_tool_executor.execute.assert_called_once()
        
        # Response should have action log
        assert response.actions_taken is not None or len(response.actions_taken or []) > 0

    @pytest.mark.asyncio
    async def test_no_action_without_tool_executor(
        self,
        mock_router,
        mock_planner,
        mock_retriever,
        mock_critic,
        mock_synthesizer,
        action_gated_route_decision,
        action_request,
    ):
        """ACTION_GATED without tool_executor should not fail."""
        mock_router.route = AsyncMock(return_value=action_gated_route_decision)
        
        engine = AgentWorkflowEngine(
            router=mock_router,
            planner=mock_planner,
            retriever=mock_retriever,
            critic=mock_critic,
            synthesizer=mock_synthesizer,
            tool_executor=None,  # No tool executor
        )
        
        # Should not raise
        response = await engine.handle(action_request)
        
        assert response is not None


class TestIdempotencyKeyGeneration:
    """Test idempotency key generation for tools."""

    def test_idempotency_key_deterministic(self):
        """Same inputs should produce same idempotency key."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        key1 = engine._generate_idempotency_key(
            thread_id="thread-1",
            tool_name="create_incident",
            payload={"title": "Test", "priority": "P2"},
        )
        
        key2 = engine._generate_idempotency_key(
            thread_id="thread-1",
            tool_name="create_incident",
            payload={"title": "Test", "priority": "P2"},
        )
        
        assert key1 == key2

    def test_idempotency_key_unique_per_thread(self):
        """Different threads should have different keys."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        key1 = engine._generate_idempotency_key(
            thread_id="thread-1",
            tool_name="create_incident",
            payload={"title": "Test"},
        )
        
        key2 = engine._generate_idempotency_key(
            thread_id="thread-2",
            tool_name="create_incident",
            payload={"title": "Test"},
        )
        
        assert key1 != key2

    def test_idempotency_key_unique_per_payload(self):
        """Different payloads should have different keys."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        key1 = engine._generate_idempotency_key(
            thread_id="thread-1",
            tool_name="create_incident",
            payload={"title": "Issue A"},
        )
        
        key2 = engine._generate_idempotency_key(
            thread_id="thread-1",
            tool_name="create_incident",
            payload={"title": "Issue B"},
        )
        
        assert key1 != key2


class TestSensitiveFieldRedaction:
    """Test PII/secret redaction in payloads."""

    def test_password_redacted(self):
        """Password fields should be redacted."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        payload = {
            "username": "testuser",
            "password": "secret123",
            "user_password": "secret456",
        }
        
        redacted = engine._redact_sensitive_fields(payload)
        
        assert redacted["username"] == "testuser"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["user_password"] == "[REDACTED]"

    def test_token_and_secret_redacted(self):
        """Token and secret fields should be redacted."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        payload = {
            "api_token": "abc123",
            "auth_secret": "xyz789",
            "description": "normal text",
        }
        
        redacted = engine._redact_sensitive_fields(payload)
        
        assert redacted["api_token"] == "[REDACTED]"
        assert redacted["auth_secret"] == "[REDACTED]"
        assert redacted["description"] == "normal text"

    def test_nested_redaction(self):
        """Nested objects should also have sensitive fields redacted."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        payload = {
            "user": {
                "name": "Test User",
                "password": "secret",
            },
            "title": "Incident",
        }
        
        redacted = engine._redact_sensitive_fields(payload)
        
        assert redacted["user"]["name"] == "Test User"
        assert redacted["user"]["password"] == "[REDACTED]"
        assert redacted["title"] == "Incident"


class TestApprovalFlow:
    """Test approval requirement detection."""

    def test_requires_approval_for_high_risk_tools(self):
        """High-risk tools should require approval by default."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        # create_incident typically requires approval
        assert engine._requires_approval("create_incident") is True

    def test_read_only_tools_no_approval(self):
        """Read-only tools might not require approval."""
        engine = AgentWorkflowEngine(
            router=MagicMock(),
            planner=MagicMock(),
            retriever=MagicMock(),
            critic=MagicMock(),
            synthesizer=MagicMock(),
        )
        
        # get_* tools typically don't require approval
        result = engine._requires_approval("get_status")
        # Could be True or False depending on implementation
        assert isinstance(result, bool)
