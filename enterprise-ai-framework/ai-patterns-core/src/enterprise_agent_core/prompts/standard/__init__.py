"""Standard prompts for the Enterprise Agent Framework.

These prompts are versioned and tested. Do not modify without
running regression evals.
"""

from .critic_sufficiency_v1 import CRITIC_SUFFICIENCY_V1
from .citation_format_v1 import CITATION_FORMAT_V1
from .tool_payload_guard_v1 import TOOL_PAYLOAD_GUARD_V1
from .planner_decomposition_v1 import PLANNER_DECOMPOSITION_V1
from .synthesizer_v1 import SYNTHESIZER_V1

# Export all standard prompts as a dictionary
STANDARD_PROMPTS = {
    "critic_sufficiency_v1": CRITIC_SUFFICIENCY_V1,
    "citation_format_v1": CITATION_FORMAT_V1,
    "tool_payload_guard_v1": TOOL_PAYLOAD_GUARD_V1,
    "planner_decomposition_v1": PLANNER_DECOMPOSITION_V1,
    "synthesizer_v1": SYNTHESIZER_V1,
}

__all__ = [
    "CRITIC_SUFFICIENCY_V1",
    "CITATION_FORMAT_V1",
    "TOOL_PAYLOAD_GUARD_V1",
    "PLANNER_DECOMPOSITION_V1",
    "SYNTHESIZER_V1",
    "STANDARD_PROMPTS",
]
