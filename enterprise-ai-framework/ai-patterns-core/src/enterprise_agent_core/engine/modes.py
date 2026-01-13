"""Loop modes and budget for the cognitive loop.

Defines the different execution modes for latency control and
resource budgets for the actor-critic loop.
"""

from enum import Enum
from pydantic import BaseModel, Field


class LoopMode(str, Enum):
    """Execution mode for the cognitive loop.

    Controls which steps are executed and whether the
    actor-critic loop is engaged.
    """

    FAST_RAG = "fast_rag"
    """Skip planning, no critic loop.
    Path: Retrieve -> Synthesize
    Use for: Simple Q&A, low-latency requirements
    """

    PLAN_RAG = "plan_rag"
    """Plan queries but no critic loop.
    Path: Plan -> Retrieve -> Synthesize
    Use for: Complex queries needing decomposition
    """

    FULL_ACTOR_CRITIC = "full_actor_critic"
    """Full cognitive loop with critic.
    Path: Plan -> Retrieve -> Critic -> (loop) -> Synthesize
    Use for: High-quality answers requiring validation
    """

    ACTION_GATED = "action_gated"
    """Full loop with human approval for actions.
    Path: Plan -> Retrieve -> Critic -> Synthesize -> (Approval) -> Act
    Use for: ServiceNow tickets, data modifications
    """


class LoopBudget(BaseModel):
    """Resource budget for the actor-critic loop.

    Enforces limits on iterations, time, and tokens to
    prevent runaway loops.
    """

    max_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum actor-critic loop iterations"
    )

    max_latency_ms: int = Field(
        default=8000,
        ge=1000,
        le=60000,
        description="Maximum total latency in milliseconds"
    )

    max_prompt_tokens: int = Field(
        default=4000,
        ge=100,
        description="Maximum tokens in prompts"
    )

    max_output_tokens: int = Field(
        default=2000,
        ge=100,
        description="Maximum tokens in outputs"
    )

    max_retrieval_chunks: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum chunks per retrieval"
    )

    class Config:
        frozen = True  # Budget is immutable once set
