"""Classic Router implementation.

Provides stable, deterministic routing based on keyword matching
and configuration rules. This is the recommended router for production.
"""

import logging
from typing import Dict, List, Optional

from ...contracts.request import AgentRequest, AgentContext
from ...interfaces.router import RouteDecision
from ...config import AgentConfig
from ..modes import LoopMode

logger = logging.getLogger(__name__)


class ClassicRouter:
    """Classic keyword-based router.

    Provides stable, deterministic routing using:
    - Keyword matching for intent classification
    - Configuration-based loop mode selection
    - Tool permission enforcement

    This router is recommended for production use.
    Use MAFRouter only when multi-agent coordination is needed.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        default_loop_mode: LoopMode = LoopMode.PLAN_RAG,
        agent_map: Optional[Dict[str, str]] = None,
    ):
        """Initialize the classic router.

        Args:
            config: Agent configuration
            default_loop_mode: Default loop mode if not matched
            agent_map: Map of capability names to agent IDs
        """
        self.config = config
        self.default_loop_mode = default_loop_mode
        self.agent_map = agent_map or {}

        # Keyword to loop mode mapping
        self.mode_keywords = {
            LoopMode.FAST_RAG: [
                "quick", "simple", "what is", "define", "list"
            ],
            LoopMode.FULL_ACTOR_CRITIC: [
                "detailed", "comprehensive", "analyze", "compare", "explain"
            ],
            LoopMode.ACTION_GATED: [
                "create ticket", "update", "submit", "request",
                "open incident", "action"
            ],
        }

        # Capability keywords for routing to different agents
        self.capability_keywords = {
            "hr": ["vacation", "policy", "hr", "leave", "benefits", "onboarding"],
            "it": ["ticket", "incident", "password", "access", "vpn", "laptop"],
            "confluence": ["documentation", "wiki", "process", "procedure"],
            "sharepoint": ["document", "file", "contract", "procurement"],
            "servicenow": ["incident", "change", "request", "service"],
        }

    async def route(
        self,
        request: AgentRequest,
        ctx: AgentContext
    ) -> RouteDecision:
        """Route the request to an appropriate agent/capability.

        Args:
            request: The incoming agent request
            ctx: Current agent context

        Returns:
            RouteDecision with agent selection and loop mode
        """
        query_lower = request.user_query.lower()

        # Determine loop mode
        loop_mode = self._determine_loop_mode(query_lower)

        # Determine target capability
        capability = self._determine_capability(query_lower)

        # Get agent ID if available
        agent_id = self.agent_map.get(capability)

        # Determine allowed tools
        tools_allowed = self._get_allowed_tools(loop_mode, capability)

        # Determine retriever type based on capability
        retriever_type = self._determine_retriever(capability)

        logger.info(
            f"Routed to capability '{capability}' with mode '{loop_mode.value}', "
            f"retriever: {retriever_type}"
        )

        return RouteDecision(
            agent_name=capability,
            agent_id=agent_id,
            loop_mode=loop_mode.value,
            tools_allowed=tools_allowed,
            confidence=1.0,  # Classic router is deterministic
            retriever_type=retriever_type,
            index_name=self._get_index_name(capability),
            routing_reason=f"Keyword match for capability: {capability}",
        )

    def _determine_loop_mode(self, query: str) -> LoopMode:
        """Determine the loop mode based on query keywords and config.

        Respects workflow.allowed_modes and workflow.router_can_override
        from the agent configuration.
        """
        # Get default mode from config
        default_mode = self.default_loop_mode
        if self.config:
            default_mode = self.config.workflow.default_mode

        # If router cannot override, return config default
        if self.config and not self.config.workflow.router_can_override:
            logger.debug(f"Router override disabled, using default: {default_mode}")
            return default_mode

        # Detect candidate mode from keywords
        candidate = self._keyword_based_mode(query)

        # Validate candidate against allowed_modes
        if self.config and self.config.workflow.allowed_modes:
            if candidate in self.config.workflow.allowed_modes:
                return candidate
            else:
                logger.debug(
                    f"Candidate mode {candidate.value} not in allowed_modes, "
                    f"using default: {default_mode}"
                )
                return default_mode

        return candidate if candidate else default_mode

    def _keyword_based_mode(self, query: str) -> LoopMode:
        """Detect loop mode candidate from query keywords."""
        # Check for ACTION_GATED first (most restrictive)
        for keyword in self.mode_keywords[LoopMode.ACTION_GATED]:
            if keyword in query:
                return LoopMode.ACTION_GATED

        # Check for FULL_ACTOR_CRITIC
        for keyword in self.mode_keywords[LoopMode.FULL_ACTOR_CRITIC]:
            if keyword in query:
                return LoopMode.FULL_ACTOR_CRITIC

        # Check for FAST_RAG
        for keyword in self.mode_keywords[LoopMode.FAST_RAG]:
            if keyword in query:
                return LoopMode.FAST_RAG

        # Use config default or class default
        if self.config and self.config.loop_mode:
            return self.config.loop_mode

        return self.default_loop_mode

    def _determine_capability(self, query: str) -> str:
        """Determine the target capability based on keywords."""
        scores = {}

        for capability, keywords in self.capability_keywords.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > 0:
                scores[capability] = score

        if scores:
            # Return highest scoring capability
            return max(scores, key=scores.get)

        # Default capability
        return "general"

    def _get_allowed_tools(
        self,
        loop_mode: LoopMode,
        capability: str
    ) -> List[str]:
        """Get the list of allowed tools for this request."""
        # Only ACTION_GATED mode allows tools
        if loop_mode != LoopMode.ACTION_GATED:
            return []

        # Capability-specific tools
        tool_map = {
            "servicenow": ["create_incident", "update_incident", "close_incident"],
            "it": ["create_ticket", "reset_password", "grant_access"],
            "hr": ["submit_request", "create_ticket"],
        }

        base_tools = tool_map.get(capability, [])

        # Filter by config if available
        if self.config and self.config.tools_allowed:
            return [t for t in base_tools if t in self.config.tools_allowed]

        return base_tools

    def _determine_retriever(self, capability: str) -> str:
        """Determine which retriever to use based on capability."""
        retriever_map = {
            "confluence": "ai_search",
            "sharepoint": "ai_search",
            "servicenow": "ai_search",
            "hr": "ai_search",
            "it": "ai_search",
            "general": "ai_search",
        }

        return retriever_map.get(capability, "ai_search")

    def _get_index_name(self, capability: str) -> Optional[str]:
        """Get the search index name for a capability."""
        if self.config and self.config.knowledge.index_name:
            return self.config.knowledge.index_name

        # Default index naming convention
        index_map = {
            "confluence": "idx-confluence",
            "sharepoint": "idx-sharepoint",
            "servicenow": "idx-servicenow",
            "hr": "idx-hr-policies",
            "it": "idx-it-kb",
        }

        return index_map.get(capability)
