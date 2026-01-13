"""Router interface and route decision contract.

The router decides which agent/capability to invoke and what loop mode to use.
Supports ClassicRouter (stable) and MAFRouter (preview) implementations.
"""

from typing import List, Optional, Protocol, runtime_checkable
from pydantic import Field

from ..contracts.base import BaseContract
from ..contracts.request import AgentRequest, AgentContext


class RouteDecision(BaseContract):
    """Decision output from the router.

    Specifies which agent to invoke, what loop mode to use,
    and what tools are allowed.
    """

    # Agent selection
    agent_name: str = Field(..., description="Name of the agent/capability to invoke")
    agent_id: Optional[str] = Field(
        default=None,
        description="Azure AI Foundry Agent ID if using atomic agents"
    )

    # Loop mode
    loop_mode: str = Field(
        default="plan_rag",
        description="Loop mode: fast_rag, plan_rag, full_actor_critic, action_gated"
    )

    # Tool permissions
    tools_allowed: List[str] = Field(
        default_factory=list,
        description="List of tool names this request is allowed to invoke"
    )

    # Routing confidence
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the routing decision"
    )

    # Retrieval configuration
    retriever_type: str = Field(
        default="ai_search",
        description="Retriever to use: ai_search, foundry_iq, confluence, sharepoint"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Azure AI Search index or Foundry IQ KB name"
    )

    # Routing metadata
    routing_reason: Optional[str] = Field(
        default=None,
        description="Explanation of why this route was chosen"
    )


@runtime_checkable
class IEnterpriseRouter(Protocol):
    """Interface for enterprise routing.

    The router examines the request and decides:
    - Which agent/capability to use
    - What loop mode to apply
    - What tools are allowed

    Implementations:
    - ClassicRouter: Stable, keyword/intent-based routing
    - MAFRouter: Preview, uses Microsoft Agent Framework for routing
    """

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
        ...
