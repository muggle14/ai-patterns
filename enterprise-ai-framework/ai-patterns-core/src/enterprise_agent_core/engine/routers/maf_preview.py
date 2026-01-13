"""Microsoft Agent Framework (MAF) Router - PREVIEW.

This router uses the Microsoft Agent Framework for multi-agent
coordination and routing. It is in preview status and should
only be used when MAF-specific features are required.

STABILITY WARNING:
- MAF APIs may change between versions
- Always have ClassicRouter as fallback
- Pin MAF version in requirements (agent-framework==0.x.y)

Feature Flag:
- Set ROUTER_MODE=maf to enable
- Defaults to fallback mode if MAF not available
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple

from ...contracts.request import AgentRequest, AgentContext
from ...interfaces.router import RouteDecision
from ...config import AgentConfig, RetrieverMode
from ..modes import LoopMode

logger = logging.getLogger(__name__)


# Intent patterns with weights for classification
_INTENT_PATTERNS = {
    "action": {
        "patterns": [
            r"\b(create|open|submit|file|update|change|modify|add|set)\b.*\b(ticket|incident|request|issue)\b",
            r"\b(please|can you|could you)\b.*(create|open|update|change)",
            r"\bI want to\b.*(create|update|file|submit)",
        ],
        "mode": LoopMode.ACTION_GATED,
        "weight": 1.0,
    },
    "complex_analysis": {
        "patterns": [
            r"\b(compare|contrast|analyze|explain|summarize|difference)\b",
            r"\b(how|why|what).*\b(work|happen|different|similar)\b",
            r"\bmultiple\b|\bseveral\b|\bvarious\b",
        ],
        "mode": LoopMode.FULL_ACTOR_CRITIC,
        "weight": 0.8,
    },
    "simple_lookup": {
        "patterns": [
            r"^what is\b",
            r"\b(where|when|who)\b.*\?$",
            r"^(find|show|get|list)\b",
        ],
        "mode": LoopMode.FAST_RAG,
        "weight": 0.6,
    },
}


class MAFRouter:
    """Microsoft Agent Framework router (PREVIEW).

    Uses MAF for intelligent multi-agent routing when:
    - Complex queries require multiple agents
    - Dynamic agent selection is needed
    - GroupChat patterns are beneficial

    IMPORTANT: This is a preview implementation.
    - Check ROUTER_MODE env var for feature flag
    - Falls back to intent-based routing if MAF unavailable
    - Enforces allowed_modes from config

    For production, prefer ClassicRouter unless MAF
    features are specifically required.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        default_loop_mode: LoopMode = LoopMode.PLAN_RAG,
        agent_map: Optional[Dict[str, str]] = None,
    ):
        """Initialize the MAF router.

        Args:
            config: Agent configuration
            default_loop_mode: Default loop mode
            agent_map: Map of capability names to agent IDs
        """
        self.config = config or AgentConfig()
        self.default_loop_mode = default_loop_mode
        self.agent_map = agent_map or {}

        # Get workflow settings
        self.allowed_modes = [m.value for m in self.config.workflow.allowed_modes]
        self.router_can_override = self.config.workflow.router_can_override
        self.tools_allowed = self.config.tools_allowed

        # Check feature flag
        self.maf_enabled = os.environ.get("ROUTER_MODE", "classic") == "maf"

        if self.maf_enabled:
            logger.warning(
                "MAFRouter enabled (PREVIEW). "
                "This router uses preview Microsoft Agent Framework APIs. "
                "Ensure you have pinned the agent-framework version."
            )
            self._maf_client = self._init_maf()
        else:
            logger.info("MAFRouter using intent-based fallback (ROUTER_MODE != maf)")
            self._maf_client = None

    def _init_maf(self):
        """Initialize MAF client.

        Returns:
            MAF Router client or None if not available
        """
        try:
            # Attempt to import MAF (when available)
            # from autogen_agentchat import Router
            # return Router(agents=[...], selection_strategy="semantic")
            logger.info("MAF client initialization - package not yet available")
            return None
        except ImportError:
            logger.warning(
                "agent-framework not installed. "
                "MAFRouter will use intent-based fallback."
            )
            return None

    async def route(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RouteDecision:
        """Route using MAF or intent-based fallback.

        Args:
            request: The incoming agent request
            ctx: Current agent context

        Returns:
            RouteDecision with agent selection, mode, and tools
        """
        if self.maf_enabled and self._maf_client:
            decision = await self._route_with_maf(request, ctx)
        else:
            decision = await self._intent_based_route(request, ctx)

        # Enforce allowed_modes from config
        decision = self._enforce_allowed_modes(decision)

        logger.info(
            f"MAFRouter decision: mode={decision.loop_mode}, "
            f"retriever={decision.retriever_type}, "
            f"confidence={decision.confidence:.2f}"
        )

        return decision

    async def _route_with_maf(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RouteDecision:
        """Route using Microsoft Agent Framework.

        In production, this would:
        1. Submit query to MAF router
        2. Get agent selection from MAF semantic analysis
        3. Determine loop mode based on MAF analysis
        4. Extract tool requirements
        """
        logger.info(f"MAF routing for correlation_id: {ctx.correlation_id}")

        # Placeholder for MAF integration when package is available:
        # result = await self._maf_client.route(
        #     query=request.user_query,
        #     context={"thread_id": ctx.thread_id},
        # )
        # return RouteDecision(
        #     agent_name=result.selected_agent,
        #     loop_mode=self._map_maf_mode(result.mode),
        #     tools_allowed=result.recommended_tools,
        #     confidence=result.confidence,
        #     retriever_type=self._select_retriever(result),
        #     routing_reason=f"MAF: {result.reasoning}",
        # )

        # For now, use intent-based routing as fallback
        return await self._intent_based_route(request, ctx)

    async def _intent_based_route(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RouteDecision:
        """Intent-based routing using pattern matching.

        Classifies the query and determines:
        - Loop mode based on intent patterns
        - Tools allowed based on config
        - Retriever type based on config
        """
        query = request.user_query
        intent, mode, confidence = self._classify_intent(query)

        # Determine if tools are needed
        tools = []
        if mode == LoopMode.ACTION_GATED:
            tools = list(self.tools_allowed)

        # Select retriever
        retriever_type = self.config.knowledge.mode.value

        return RouteDecision(
            agent_name=intent,
            loop_mode=mode.value,
            tools_allowed=tools,
            confidence=confidence,
            retriever_type=retriever_type,
            routing_reason=f"Intent classification: {intent}",
        )

    def _classify_intent(self, query: str) -> Tuple[str, LoopMode, float]:
        """Classify query intent using pattern matching.

        Args:
            query: User query text

        Returns:
            Tuple of (intent_name, loop_mode, confidence)
        """
        query_lower = query.lower()
        best_match = None
        best_score = 0.0

        for intent_name, config in _INTENT_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    score = config["weight"]
                    if score > best_score:
                        best_score = score
                        best_match = (intent_name, config["mode"])

        if best_match:
            return (best_match[0], best_match[1], min(best_score, 0.9))
        else:
            # Default to PLAN_RAG for unclassified queries
            return ("general", self.default_loop_mode, 0.5)

    def _enforce_allowed_modes(self, decision: RouteDecision) -> RouteDecision:
        """Enforce allowed_modes from config.

        If the router selects a mode not in allowed_modes,
        fall back to the default mode.
        """
        if not self.router_can_override:
            # Router cannot override config default
            decision.loop_mode = self.default_loop_mode.value
            decision.routing_reason += " (mode locked by config)"
            return decision

        if decision.loop_mode not in self.allowed_modes:
            original_mode = decision.loop_mode
            decision.loop_mode = self.default_loop_mode.value
            decision.confidence *= 0.7  # Reduce confidence for fallback
            decision.routing_reason += f" (mode {original_mode} not allowed, using {decision.loop_mode})"
            logger.warning(
                f"Mode '{original_mode}' not in allowed_modes {self.allowed_modes}, "
                f"falling back to '{decision.loop_mode}'"
            )

        return decision

