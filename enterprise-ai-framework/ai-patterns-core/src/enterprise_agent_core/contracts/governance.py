"""Governance contracts for guardrails and compliance.

These contracts define the structure for governance checks
including PII detection, content safety, and policy enforcement.
Currently implemented as placeholders for future enhancement.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import BaseContract


class PiiMode(str, Enum):
    """PII handling mode."""
    OFF = "off"           # No PII detection
    DETECT = "detect"     # Detect and log only
    REDACT = "redact"     # Detect and redact


class ContentSafetyMode(str, Enum):
    """Content safety enforcement level."""
    OFF = "off"           # No content safety checks
    STANDARD = "standard" # Standard safety checks
    STRICT = "strict"     # Strict safety checks


class ContentBlock(BaseContract):
    """A blocked content segment."""

    category: str = Field(..., description="Block category (hate, violence, etc.)")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    start_offset: Optional[int] = Field(default=None, description="Start position in text")
    end_offset: Optional[int] = Field(default=None, description="End position in text")
    reason: Optional[str] = Field(default=None, description="Reason for block")


class GovernanceRequest(BaseContract):
    """Request for governance checks.

    Specifies what governance checks to apply to content.
    """

    # Mode configuration
    pii_mode: PiiMode = Field(
        default=PiiMode.DETECT,
        description="PII handling mode"
    )
    content_safety_mode: ContentSafetyMode = Field(
        default=ContentSafetyMode.STANDARD,
        description="Content safety check level"
    )

    # Policy set
    policy_set_id: Optional[str] = Field(
        default=None,
        description="Custom policy set ID to apply"
    )

    # Content to check
    content: Optional[str] = Field(
        default=None,
        description="Content to check (if not using context)"
    )

    # Check types
    check_input: bool = Field(
        default=True,
        description="Whether to check input content"
    )
    check_output: bool = Field(
        default=True,
        description="Whether to check output content"
    )
    check_tool_payloads: bool = Field(
        default=True,
        description="Whether to check tool payloads"
    )


class GovernanceResult(BaseContract):
    """Result of governance checks.

    Indicates whether content passed governance checks and
    any modifications or blocks applied.
    """

    # Overall result
    safe: bool = Field(..., description="Whether content passed all checks")

    # PII handling
    pii_detected: bool = Field(
        default=False,
        description="Whether PII was detected"
    )
    pii_redacted: bool = Field(
        default=False,
        description="Whether PII was redacted"
    )
    pii_types_found: List[str] = Field(
        default_factory=list,
        description="Types of PII found (email, phone, ssn, etc.)"
    )

    # Content safety
    blocks: List[ContentBlock] = Field(
        default_factory=list,
        description="Content segments that were blocked"
    )
    severity: Optional[str] = Field(
        default=None,
        description="Overall severity if issues found"
    )

    # Modified content (if redaction applied)
    redacted_content: Optional[str] = Field(
        default=None,
        description="Content with PII redacted"
    )

    # Policy results
    policies_checked: List[str] = Field(
        default_factory=list,
        description="Policy IDs that were checked"
    )
    policy_violations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Details of any policy violations"
    )
