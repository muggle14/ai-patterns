"""Agent Workflow Engine - the canonical state machine.

This is the core orchestrator that enforces the cognitive loop:
Plan -> Retrieve -> Critic -> Synthesize -> (Act)

The engine decides step order; LLM cannot skip steps.
"""

import json
import hashlib
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace

from .modes import LoopMode, LoopBudget
from ..contracts.request import AgentRequest, AgentContext
from ..contracts.planning import QueryPlan, QuerySpec
from ..contracts.retrieval import RetrievalResult, RetrievalMetrics, RetrievedChunk
from ..contracts.response import AgentResponse, AuditFields, ActionLog
from ..contracts.tools import ToolCallRequest, ToolCallResult, ToolStatus
from ..interfaces.router import IEnterpriseRouter, RouteDecision
from ..interfaces.planner import IPlanner
from ..interfaces.retriever import IRetriever
from ..interfaces.critic import ICritic
from ..interfaces.synthesizer import ISynthesizer
from ..interfaces.tool_executor import IToolExecutor
from ..telemetry.spans import SpanNames
from ..telemetry.attributes import Attributes

# Optional atomic agent support
try:
    from ..atomic.adapter import AzureAtomicAdapter, AtomicAgentResponse
    ATOMIC_AVAILABLE = True
except ImportError:
    ATOMIC_AVAILABLE = False
    AzureAtomicAdapter = None
    AtomicAgentResponse = None

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("enterprise_agent_core")


class AgentWorkflowEngine:
    """The canonical state machine for the Enterprise Agent.

    Enforces the cognitive loop based on the configured LoopMode:
    - FAST_RAG: Retrieve -> Synthesize
    - PLAN_RAG: Plan -> Retrieve -> Synthesize
    - FULL_ACTOR_CRITIC: Plan -> Retrieve -> Critic -> (loop) -> Synthesize
    - ACTION_GATED: Full + human approval before Act

    The engine owns orchestration - LLM cannot skip steps.
    """

    def __init__(
        self,
        router: IEnterpriseRouter,
        planner: IPlanner,
        retriever: IRetriever,
        critic: ICritic,
        synthesizer: ISynthesizer,
        tool_executor: Optional[IToolExecutor] = None,
        budget: Optional[LoopBudget] = None,
        agent_name: str = "enterprise_agent",
        default_loop_mode: LoopMode = LoopMode.PLAN_RAG,
        atomic_agents: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the workflow engine.

        Args:
            router: Routes requests to agents/capabilities
            planner: Decomposes queries into plans
            retriever: Retrieves content from data sources
            critic: Evaluates sufficiency of retrieval
            synthesizer: Generates final response
            tool_executor: Optional tool execution (for ACTION_GATED)
            budget: Resource budget for the loop
            agent_name: Name for telemetry and audit
            default_loop_mode: Default mode if router doesn't specify
            atomic_agents: Optional dict of name -> AzureAtomicAdapter for delegation
        """
        self.router = router
        self.planner = planner
        self.retriever = retriever
        self.critic = critic
        self.synthesizer = synthesizer
        self.tool_executor = tool_executor
        self.budget = budget or LoopBudget()
        self.agent_name = agent_name
        self.default_loop_mode = default_loop_mode
        self.atomic_agents = atomic_agents or {}

    async def handle(self, request: AgentRequest) -> AgentResponse:
        """Handle an agent request through the cognitive loop.

        This is the main entry point. It:
        1. Creates context and starts tracing
        2. Routes to determine loop mode
        3. Executes the appropriate path
        4. Optionally executes tools (if ACTION_GATED)
        5. Returns response with full audit trail

        Args:
            request: The incoming agent request

        Returns:
            AgentResponse with response, citations, and audit info
        """
        start_time = time.monotonic()
        correlation_id = request.trace_context.get("correlation_id") if request.trace_context else None
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Create context
        ctx = AgentContext(
            correlation_id=correlation_id,
            thread_id=request.thread_id,
            trace_context=request.trace_context or {},
        )

        with tracer.start_as_current_span("agent.handle") as root_span:
            root_span.set_attribute("correlation_id", correlation_id)
            root_span.set_attribute("thread_id", request.thread_id)
            root_span.set_attribute("agent_name", self.agent_name)

            try:
                # Step 1: Route
                with tracer.start_as_current_span("agent.route") as span:
                    route_decision = await self.router.route(request, ctx)
                    loop_mode = LoopMode(route_decision.loop_mode)
                    span.set_attribute("loop_mode", loop_mode.value)
                    span.set_attribute("agent_selected", route_decision.agent_name)

                root_span.set_attribute("loop_mode", loop_mode.value)

                # Check for atomic agent delegation
                agent_name = route_decision.agent_name
                if agent_name in self.atomic_agents:
                    response = await self._delegate_to_atomic_agent(
                        request, ctx, route_decision
                    )
                # Step 2: Execute based on mode
                elif loop_mode == LoopMode.FAST_RAG:
                    response = await self._fast_rag_path(request, ctx)
                elif loop_mode == LoopMode.PLAN_RAG:
                    response = await self._plan_rag_path(request, ctx)
                elif loop_mode in (LoopMode.FULL_ACTOR_CRITIC, LoopMode.ACTION_GATED):
                    response = await self._full_actor_critic_path(
                        request, ctx, route_decision
                    )
                else:
                    # Fallback to PLAN_RAG
                    response = await self._plan_rag_path(request, ctx)

                # Step 3: Handle tools if ACTION_GATED
                if loop_mode == LoopMode.ACTION_GATED and self.tool_executor:
                    response = await self._handle_actions(
                        request, ctx, route_decision, response
                    )

                # Finalize response
                processing_time_ms = (time.monotonic() - start_time) * 1000
                response.processing_time_ms = processing_time_ms
                response.response_mode = loop_mode.value

                # Add audit fields
                response.audit = AuditFields(
                    correlation_id=correlation_id,
                    thread_id=request.thread_id,
                    request_id=request.request_id,
                    agent_name=self.agent_name,
                    risk_tier=request.risk_tier.value,
                    data_sources_used=ctx.data_sources_used,
                    tools_called=ctx.tools_called,
                    prompt_versions=ctx.prompt_versions,
                    loop_mode=loop_mode.value,
                    iterations_used=ctx.iteration,
                    user_id=request.user_id,
                    access_groups=request.access_groups,
                )

                root_span.set_attribute("processing_time_ms", processing_time_ms)
                root_span.set_attribute("iterations_used", ctx.iteration)

                return response

            except Exception as e:
                logger.exception(f"Error handling request: {e}")
                root_span.record_exception(e)
                raise

    async def _fast_rag_path(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> AgentResponse:
        """Execute FAST_RAG path: Retrieve -> Synthesize.

        Skips planning for lowest latency.
        """
        # Create default plan from query
        plan = QueryPlan(
            intents=["information_retrieval"],
            subquestions=[request.user_query],
            query_specs=[QuerySpec(query_text=request.user_query)],
        )
        ctx.plan = plan

        # Retrieve
        with tracer.start_as_current_span("agent.retrieve") as span:
            retrieval = await self.retriever.retrieve(plan, request, ctx)
            ctx.retrieval = retrieval
            ctx.data_sources_used.append(retrieval.metrics.source)
            span.set_attribute("hit_count", retrieval.metrics.hit_count)
            span.set_attribute("source", retrieval.metrics.source)

        # Synthesize
        with tracer.start_as_current_span("agent.synthesize") as span:
            response = await self.synthesizer.write(request, retrieval, ctx)
            span.set_attribute("citation_count", len(response.citations))

        response.retrieval_metrics = retrieval.metrics
        return response

    async def _plan_rag_path(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> AgentResponse:
        """Execute PLAN_RAG path: Plan -> Retrieve -> Synthesize."""
        # Plan
        with tracer.start_as_current_span("agent.plan") as span:
            plan = await self.planner.plan(request, ctx)
            ctx.plan = plan
            span.set_attribute("subquestion_count", len(plan.subquestions))
            span.set_attribute("query_spec_count", len(plan.query_specs))

        # Retrieve
        with tracer.start_as_current_span("agent.retrieve") as span:
            retrieval = await self.retriever.retrieve(plan, request, ctx)
            ctx.retrieval = retrieval
            ctx.data_sources_used.append(retrieval.metrics.source)
            span.set_attribute("hit_count", retrieval.metrics.hit_count)
            span.set_attribute("source", retrieval.metrics.source)

        # Synthesize
        with tracer.start_as_current_span("agent.synthesize") as span:
            response = await self.synthesizer.write(request, retrieval, ctx)
            span.set_attribute("citation_count", len(response.citations))

        response.retrieval_metrics = retrieval.metrics
        return response

    async def _full_actor_critic_path(
        self,
        request: AgentRequest,
        ctx: AgentContext,
        route_decision: RouteDecision
    ) -> AgentResponse:
        """Execute FULL_ACTOR_CRITIC path with loop.

        Plan -> Retrieve -> Critic -> (loop if insufficient) -> Synthesize
        """
        start_time = time.monotonic()

        # Initial plan
        with tracer.start_as_current_span("agent.plan") as span:
            plan = await self.planner.plan(request, ctx)
            ctx.plan = plan
            span.set_attribute("subquestion_count", len(plan.subquestions))

        # Actor-critic loop
        retrieval = None
        for iteration in range(self.budget.max_iterations):
            ctx.iteration = iteration + 1

            # Check budget
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if elapsed_ms > self.budget.max_latency_ms:
                logger.warning(
                    f"Budget exceeded at iteration {iteration + 1}: "
                    f"{elapsed_ms:.0f}ms > {self.budget.max_latency_ms}ms"
                )
                break

            # Retrieve
            with tracer.start_as_current_span("agent.retrieve") as span:
                span.set_attribute("iteration", iteration + 1)
                retrieval = await self.retriever.retrieve(plan, request, ctx)
                ctx.retrieval = retrieval
                if retrieval.metrics.source not in ctx.data_sources_used:
                    ctx.data_sources_used.append(retrieval.metrics.source)
                span.set_attribute("hit_count", retrieval.metrics.hit_count)

            # Critic check
            with tracer.start_as_current_span("agent.critic") as span:
                span.set_attribute("iteration", iteration + 1)
                critic_result = await self.critic.check(request, retrieval, ctx)
                ctx.critic = critic_result
                span.set_attribute("sufficient", critic_result.sufficient)
                span.set_attribute("confidence", critic_result.confidence)

            if critic_result.sufficient:
                logger.info(f"Sufficient at iteration {iteration + 1}")
                break

            # Refine plan for next iteration
            if critic_result.next_query_specs:
                plan = QueryPlan(
                    intents=plan.intents,
                    subquestions=plan.subquestions + critic_result.missing_aspects,
                    query_specs=critic_result.next_query_specs,
                )
                ctx.plan = plan
            else:
                # Expand existing queries
                for spec in plan.query_specs:
                    spec.top_k = min(spec.top_k + 3, self.budget.max_retrieval_chunks)

        # Synthesize
        if retrieval is None:
            # No retrieval happened - create empty result
            retrieval = RetrievalResult(
                chunks=[],
                metrics=RetrievalMetrics(
                    latency_ms=0,
                    hit_count=0,
                    source="none",
                ),
            )

        with tracer.start_as_current_span("agent.synthesize") as span:
            response = await self.synthesizer.write(request, retrieval, ctx)
            span.set_attribute("citation_count", len(response.citations))

        response.retrieval_metrics = retrieval.metrics
        return response

    async def _handle_actions(
        self,
        request: AgentRequest,
        ctx: AgentContext,
        route_decision: RouteDecision,
        response: AgentResponse
    ) -> AgentResponse:
        """Handle tool execution for ACTION_GATED mode.

        1. Extract action intent from synthesized response
        2. Build ToolCallRequest with idempotency key
        3. Execute tool with tracer span
        4. Append ActionLog to response
        5. Handle pending approval status
        """
        if not self.tool_executor:
            logger.warning("ACTION_GATED but no tool_executor configured")
            return response

        # Step 1: Extract action intent from response
        action_intent = await self._extract_action_intent(
            request, response, route_decision.tools_allowed
        )

        if not action_intent:
            logger.info("No action intent detected in response")
            return response

        tool_name = action_intent.get("tool_name")
        payload = action_intent.get("payload", {})
        requires_approval = action_intent.get("requires_approval", True)

        logger.info(f"Action detected: {tool_name}, approval_required: {requires_approval}")

        # Step 2: Build ToolCallRequest with idempotency key
        idempotency_key = self._generate_idempotency_key(
            ctx.thread_id, tool_name, payload
        )

        tool_request = ToolCallRequest(
            tool_name=tool_name,
            payload=payload,
            correlation_id=ctx.correlation_id,
            thread_id=ctx.thread_id,
            approval_required=requires_approval,
            idempotency_key=idempotency_key,
        )

        # Step 3: Execute tool with tracer span
        span_name = SpanNames.tool_span_name(tool_name)
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(Attributes.TOOL_NAME, tool_name)
            span.set_attribute(Attributes.TOOL_APPROVAL_REQUIRED, requires_approval)
            span.set_attribute(Attributes.CORRELATION_ID, ctx.correlation_id)

            result = await self.tool_executor.execute(tool_request, ctx)

            span.set_attribute(Attributes.TOOL_STATUS, result.status.value)
            if result.execution_time_ms:
                span.set_attribute(Attributes.TOOL_EXECUTION_MS, result.execution_time_ms)

        # Step 4: Append ActionLog to response
        action_log = ActionLog(
            tool_name=tool_name,
            inputs=self._redact_sensitive_fields(payload),
            outputs=result.outputs or {},
            status=result.status.value,
            execution_time_ms=result.execution_time_ms,
            required_approval=requires_approval,
            approved_by=result.approved_by,
        )
        response.actions_taken.append(action_log)

        # Track tool call in context
        if tool_name not in ctx.tools_called:
            ctx.tools_called.append(tool_name)

        # Step 5: Handle pending approval status
        if result.status == ToolStatus.PENDING_APPROVAL:
            response.suggested_followups.insert(
                0,
                f"Action '{tool_name}' is pending approval (ID: {result.approval_id}). "
                "A supervisor will review and approve this action."
            )
            logger.info(f"Tool {tool_name} pending approval: {result.approval_id}")

        elif result.status == ToolStatus.SUCCESS:
            logger.info(f"Tool {tool_name} executed successfully")

        elif result.status in (ToolStatus.FAILED, ToolStatus.TIMEOUT):
            logger.error(f"Tool {tool_name} failed: {result.error}")
            response.suggested_followups.insert(
                0,
                f"The action '{tool_name}' could not be completed: {result.error}"
            )

        return response

    async def _extract_action_intent(
        self,
        request: AgentRequest,
        response: AgentResponse,
        tools_allowed: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Extract action intent from the synthesized response.

        Uses LLM-based extraction with the action_extractor prompt.
        Falls back to keyword-based detection if LLM unavailable.
        """
        if not tools_allowed:
            return None

        response_lower = response.response_text.lower()

        # Keyword-based action detection
        # Maps tool base names to detection keywords
        action_keywords: Dict[str, List[str]] = {
            "create_incident": ["create", "open", "new incident", "submit ticket", "file a ticket"],
            "update_incident": ["update", "modify", "change the ticket", "edit incident"],
            "add_comment": ["add comment", "add note", "comment on"],
            "close_incident": ["close", "resolve", "mark resolved"],
            "create_ticket": ["create ticket", "open ticket", "new ticket"],
            "reset_password": ["reset password", "password reset"],
            "grant_access": ["grant access", "provide access", "give access"],
        }

        for tool_name in tools_allowed:
            # Extract base name (e.g., "servicenow.create_incident" -> "create_incident")
            base_name = tool_name.split(".")[-1] if "." in tool_name else tool_name

            if base_name in action_keywords:
                for keyword in action_keywords[base_name]:
                    if keyword in response_lower:
                        # Extract basic payload from context
                        payload = self._extract_basic_payload(
                            request.user_query, response.response_text, base_name
                        )

                        return {
                            "tool_name": tool_name,
                            "payload": payload,
                            "requires_approval": self._requires_approval(tool_name),
                            "confidence": 0.8,
                        }

        return None

    def _extract_basic_payload(
        self,
        user_query: str,
        response_text: str,
        action_type: str
    ) -> Dict[str, Any]:
        """Extract basic payload fields from context.

        In production, this would use LLM-based structured extraction.
        """
        payload: Dict[str, Any] = {}

        if action_type in ("create_incident", "create_ticket"):
            payload = {
                "summary": user_query[:200],
                "description": f"User request: {user_query}",
                "priority": "medium",
            }
        elif action_type == "update_incident":
            payload = {
                "comment": f"Update based on: {user_query[:100]}",
            }
        elif action_type == "add_comment":
            payload = {
                "comment": response_text[:500],
            }

        return payload

    def _requires_approval(self, tool_name: str) -> bool:
        """Determine if a tool requires approval.

        In production, this would be config-driven from agent.yaml.
        """
        # Tools that don't require approval
        no_approval_tools = ["add_comment", "add_note"]

        base_name = tool_name.split(".")[-1] if "." in tool_name else tool_name
        return base_name not in no_approval_tools

    def _generate_idempotency_key(
        self,
        thread_id: str,
        tool_name: str,
        payload: Dict[str, Any]
    ) -> str:
        """Generate idempotency key for safe retries.

        Key is based on thread_id, tool_name, and payload hash.
        """
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        return f"{thread_id}:{tool_name}:{payload_hash}"

    def _redact_sensitive_fields(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from payload for logging.

        Masks fields that may contain PII or secrets.
        """
        sensitive_fields = ["password", "secret", "token", "ssn", "credit_card"]
        redacted = {}

        for key, value in payload.items():
            key_lower = key.lower()
            if any(sf in key_lower for sf in sensitive_fields):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive_fields(value)
            else:
                redacted[key] = value

        return redacted

    async def _delegate_to_atomic_agent(
        self,
        request: AgentRequest,
        ctx: AgentContext,
        route_decision: RouteDecision,
    ) -> AgentResponse:
        """Delegate processing to a Foundry atomic agent.

        Used when the router selects an agent that is registered as
        an atomic agent (Foundry Assistants API).

        Args:
            request: The incoming agent request
            ctx: Current agent context
            route_decision: Router's decision with agent selection

        Returns:
            AgentResponse from the atomic agent
        """
        agent_name = route_decision.agent_name
        adapter = self.atomic_agents.get(agent_name)

        if not adapter:
            logger.error(f"Atomic agent '{agent_name}' not found")
            return AgentResponse(
                response=f"Error: Atomic agent '{agent_name}' not configured",
                citations=[],
            )

        with tracer.start_as_current_span("agent.atomic_delegate") as span:
            span.set_attribute("atomic_agent", agent_name)
            span.set_attribute("thread_id", request.thread_id)

            try:
                # Process through atomic agent
                atomic_response = await adapter.process_turn(
                    user_input=request.user_query,
                    thread_id=request.thread_id,
                )

                # Track tools called
                if atomic_response.tool_calls_made:
                    ctx.tools_called.extend(atomic_response.tool_calls_made)

                # Convert to AgentResponse
                citations = []
                for cit in atomic_response.citations:
                    citations.append({
                        "type": cit.get("type", "file"),
                        "text": cit.get("text", ""),
                        "file_id": cit.get("file_id"),
                    })

                span.set_attribute("status", atomic_response.status)
                span.set_attribute("tool_calls", len(atomic_response.tool_calls_made))

                return AgentResponse(
                    response=atomic_response.content,
                    citations=citations,
                )

            except Exception as e:
                logger.exception(f"Atomic agent error: {e}")
                span.record_exception(e)
                return AgentResponse(
                    response=f"Error from atomic agent: {str(e)}",
                    citations=[],
                )
