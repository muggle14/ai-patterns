"""Unit tests for contract validation."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from enterprise_agent_core.contracts.base import BaseContract
from enterprise_agent_core.contracts.request import (
    AgentRequest,
    AgentContext,
    RiskTier,
)
from enterprise_agent_core.contracts.planning import QueryPlan, QuerySpec, SearchMode
from enterprise_agent_core.contracts.retrieval import (
    RetrievalResult,
    RetrievedChunk,
    RetrievalMetrics,
)
from enterprise_agent_core.contracts.critic import SufficiencyResult
from enterprise_agent_core.contracts.tools import (
    ToolCallRequest,
    ToolCallResult,
    ToolStatus,
)
from enterprise_agent_core.contracts.governance import (
    GovernanceRequest,
    GovernanceResult,
    PiiMode,
    ContentSafetyMode,
)
from enterprise_agent_core.contracts.response import (
    AgentResponse,
    Citation,
    ActionLog,
    AuditFields,
)


class TestBaseContract:
    """Tests for BaseContract."""

    def test_schema_version_default(self):
        """Test that schema_version has default value."""

        class TestContract(BaseContract):
            pass

        contract = TestContract()
        assert contract.schema_version == "1.0.0"

    def test_created_at_auto_set(self):
        """Test that created_at is automatically set."""

        class TestContract(BaseContract):
            pass

        before = datetime.now(timezone.utc)
        contract = TestContract()
        after = datetime.now(timezone.utc)

        assert before <= contract.created_at <= after


class TestAgentRequest:
    """Tests for AgentRequest contract."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            AgentRequest()  # Missing required fields

    def test_valid_request(self):
        """Test creating a valid request."""
        request = AgentRequest(
            request_id="req-123",
            thread_id="thread-456",
            user_query="What is the policy?",
        )
        assert request.request_id == "req-123"
        assert request.thread_id == "thread-456"
        assert request.user_query == "What is the policy?"
        assert request.schema_version == "1.0.0"

    def test_default_risk_tier(self):
        """Test default risk tier is TIER2."""
        request = AgentRequest(
            request_id="req-123",
            thread_id="thread-456",
            user_query="test",
        )
        assert request.risk_tier == RiskTier.TIER2

    def test_mutable_defaults_isolated(self):
        """Test that mutable defaults are isolated between instances."""
        r1 = AgentRequest(
            request_id="1",
            thread_id="t1",
            user_query="q1",
        )
        r2 = AgentRequest(
            request_id="2",
            thread_id="t2",
            user_query="q2",
        )

        r1.metadata["key"] = "value"
        assert "key" not in r2.metadata

        r1.access_groups.append("group1")
        assert "group1" not in r2.access_groups


class TestAgentContext:
    """Tests for AgentContext contract."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            AgentContext()  # Missing required fields

    def test_valid_context(self):
        """Test creating a valid context."""
        ctx = AgentContext(
            correlation_id="corr-123",
            thread_id="thread-456",
        )
        assert ctx.correlation_id == "corr-123"
        assert ctx.iteration == 0

    def test_mutable_defaults_isolated(self):
        """Test that mutable defaults are isolated."""
        c1 = AgentContext(correlation_id="1", thread_id="t1")
        c2 = AgentContext(correlation_id="2", thread_id="t2")

        c1.data_sources_used.append("source1")
        assert "source1" not in c2.data_sources_used

        c1.tools_called.append("tool1")
        assert "tool1" not in c2.tools_called


class TestQuerySpec:
    """Tests for QuerySpec contract."""

    def test_required_fields(self):
        """Test that query_text is required."""
        with pytest.raises(ValidationError):
            QuerySpec()

    def test_defaults(self):
        """Test default values."""
        spec = QuerySpec(query_text="test query")
        assert spec.top_k == 5
        assert spec.mode == SearchMode.HYBRID
        assert spec.rerank is False

    def test_top_k_validation(self):
        """Test top_k bounds validation."""
        with pytest.raises(ValidationError):
            QuerySpec(query_text="test", top_k=0)

        with pytest.raises(ValidationError):
            QuerySpec(query_text="test", top_k=100)


class TestRetrievalResult:
    """Tests for RetrievalResult contract."""

    def test_mutable_defaults_isolated(self):
        """Test that chunks list is isolated between instances."""
        r1 = RetrievalResult(
            chunks=[],
            metrics=RetrievalMetrics(latency_ms=100, hit_count=0, source="test"),
        )
        r2 = RetrievalResult(
            chunks=[],
            metrics=RetrievalMetrics(latency_ms=100, hit_count=0, source="test"),
        )

        r1.chunks.append(
            RetrievedChunk(
                content_id="1",
                title="Test",
                snippet="content",
                score=0.9,
                source_system="test",
            )
        )
        assert len(r2.chunks) == 0


class TestSufficiencyResult:
    """Tests for SufficiencyResult contract."""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError):
            SufficiencyResult()

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            SufficiencyResult(sufficient=True, confidence=1.5)

        with pytest.raises(ValidationError):
            SufficiencyResult(sufficient=True, confidence=-0.1)

    def test_valid_result(self):
        """Test valid sufficiency result."""
        result = SufficiencyResult(
            sufficient=True,
            confidence=0.9,
        )
        assert result.sufficient is True
        assert result.confidence == 0.9
        assert result.missing_aspects == []


class TestToolCallRequest:
    """Tests for ToolCallRequest contract."""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError):
            ToolCallRequest()

    def test_valid_request(self):
        """Test valid tool call request."""
        request = ToolCallRequest(
            tool_name="create_ticket",
            payload={"title": "Test", "description": "Issue"},
        )
        assert request.tool_name == "create_ticket"
        assert request.approval_required is False
        assert request.timeout_ms == 30000


class TestToolCallResult:
    """Tests for ToolCallResult contract."""

    def test_status_enum(self):
        """Test status enum values."""
        result = ToolCallResult(status=ToolStatus.SUCCESS)
        assert result.status == ToolStatus.SUCCESS

        result = ToolCallResult(status=ToolStatus.PENDING_APPROVAL)
        assert result.status == ToolStatus.PENDING_APPROVAL


class TestGovernanceContracts:
    """Tests for governance contracts."""

    def test_governance_request_defaults(self):
        """Test default values for governance request."""
        request = GovernanceRequest()
        assert request.pii_mode == PiiMode.DETECT
        assert request.content_safety_mode == ContentSafetyMode.STANDARD

    def test_governance_result(self):
        """Test governance result."""
        result = GovernanceResult(safe=True)
        assert result.safe is True
        assert result.pii_detected is False


class TestAgentResponse:
    """Tests for AgentResponse contract."""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError):
            AgentResponse()

    def test_valid_response(self):
        """Test valid response."""
        response = AgentResponse(
            thread_id="thread-123",
            response_text="Here is the answer...",
        )
        assert response.thread_id == "thread-123"
        assert response.citations == []
        assert response.processing_time_ms == 0.0

    def test_with_citations(self):
        """Test response with citations."""
        response = AgentResponse(
            thread_id="thread-123",
            response_text="Based on [1]...",
            citations=[
                Citation(
                    content_id="doc-1",
                    snippet="Source content...",
                    confidence_score=0.95,
                )
            ],
        )
        assert len(response.citations) == 1
        assert response.citations[0].confidence_score == 0.95


class TestAuditFields:
    """Tests for AuditFields contract."""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError):
            AuditFields()

    def test_valid_audit_fields(self):
        """Test valid audit fields."""
        audit = AuditFields(
            correlation_id="corr-123",
            thread_id="thread-456",
            request_id="req-789",
            agent_name="test-agent",
            loop_mode="plan_rag",
        )
        assert audit.correlation_id == "corr-123"
        assert audit.risk_tier == "tier2"  # Default
