"""Standard telemetry attributes for Enterprise Agent.

Defines consistent attribute names for OpenTelemetry spans
across all components of the cognitive loop.
"""


class Attributes:
    """Standard attribute names for telemetry.

    Use these constants to ensure consistent attribute naming
    across all spans in the Enterprise Agent framework.

    These attributes enable:
    - Filtering traces by agent, thread, or correlation
    - Analyzing loop performance and iteration counts
    - Debugging retrieval quality issues
    - Tracking prompt versions for regression analysis
    """

    # Request identification
    CORRELATION_ID = "agent.correlation_id"
    THREAD_ID = "agent.thread_id"
    REQUEST_ID = "agent.request_id"

    # Agent identification
    AGENT_NAME = "agent.name"
    PROJECT_NAME = "agent.project_name"
    AGENT_VERSION = "agent.version"

    # Loop tracking
    LOOP_MODE = "agent.loop_mode"
    ITERATION = "agent.iteration"
    MAX_ITERATIONS = "agent.max_iterations"

    # Risk and governance
    RISK_TIER = "agent.risk_tier"
    GOVERNANCE_SAFE = "agent.governance.safe"
    PII_DETECTED = "agent.governance.pii_detected"

    # Routing
    ROUTE_CAPABILITY = "agent.route.capability"
    ROUTE_CONFIDENCE = "agent.route.confidence"
    ROUTER_TYPE = "agent.route.router_type"

    # Planning
    SUBQUESTION_COUNT = "agent.plan.subquestion_count"
    QUERY_SPEC_COUNT = "agent.plan.query_spec_count"
    INTENTS = "agent.plan.intents"

    # Retrieval
    RETRIEVAL_SOURCE = "agent.retrieval.source"
    RETRIEVAL_INDEX = "agent.retrieval.index"
    RETRIEVAL_TOP_K = "agent.retrieval.top_k"
    RETRIEVAL_HIT_COUNT = "agent.retrieval.hit_count"
    RETRIEVAL_FILTERS = "agent.retrieval.filters"
    RETRIEVAL_LATENCY_MS = "agent.retrieval.latency_ms"
    RETRIEVAL_MODE = "agent.retrieval.mode"

    # Critic
    CRITIC_SUFFICIENT = "agent.critic.sufficient"
    CRITIC_CONFIDENCE = "agent.critic.confidence"
    CRITIC_MISSING_COUNT = "agent.critic.missing_aspects_count"

    # Synthesis
    CITATION_COUNT = "agent.synthesis.citation_count"
    RESPONSE_LENGTH = "agent.synthesis.response_length"
    FOLLOWUP_COUNT = "agent.synthesis.followup_count"

    # Tool execution
    TOOL_NAME = "agent.tool.name"
    TOOL_STATUS = "agent.tool.status"
    TOOL_EXECUTION_MS = "agent.tool.execution_ms"
    TOOL_APPROVAL_REQUIRED = "agent.tool.approval_required"

    # Prompt tracking
    PROMPT_VERSION = "agent.prompt.version"
    PROMPT_NAME = "agent.prompt.name"
    PROMPT_HASH = "agent.prompt.hash"

    # Performance
    PROCESSING_TIME_MS = "agent.processing_time_ms"
    TOKEN_COUNT_INPUT = "agent.tokens.input"
    TOKEN_COUNT_OUTPUT = "agent.tokens.output"

    # Errors
    ERROR_TYPE = "agent.error.type"
    ERROR_MESSAGE = "agent.error.message"
