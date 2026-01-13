"""Base contract for all Enterprise Agent models.

Designed for Azure AI Foundry integration with proper schema versioning
and audit trail support.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class BaseContract(BaseModel):
    """Base class for all Enterprise Agent contracts.

    Provides:
    - schema_version for contract evolution and compatibility
    - created_at timestamp for auditing (UTC)
    - Strict validation (no extra fields allowed)

    All contracts inherit from this to ensure consistent versioning
    across the Azure AI Foundry agent ecosystem.
    """

    schema_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        extra="forbid",
        validate_default=True,
        str_strip_whitespace=True,
    )
