"""Standard prompts for the Enterprise Agent Framework.

This module provides versioned prompt templates for the cognitive loop.
All prompts are versioned and their versions are logged in traces and responses.

Standard prompts (patterns repo):
- critic_sufficiency_v1: Evaluates retrieval sufficiency
- citation_format_v1: Formats responses with proper citations
- tool_payload_guard_v1: Validates tool payloads before execution
- planner_decomposition_v1: Decomposes complex queries

Project prompts (projects repo):
- Override these in use-cases/{bot}/prompts/ for domain-specific behavior
"""

from .loader import PromptLoader, PromptPack
from .standard import STANDARD_PROMPTS

__all__ = [
    "PromptLoader",
    "PromptPack",
    "STANDARD_PROMPTS",
]
