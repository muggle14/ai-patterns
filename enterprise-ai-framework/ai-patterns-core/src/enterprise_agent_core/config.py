"""Configuration schemas for Enterprise Agent.

Defines configuration models for the agent, including Azure AI Foundry
settings, loop modes, governance options, and security configurations.

Production-safe defaults:
- CORS: No wildcard origins (explicit allowlist required)
- mock_mode: Disabled by default (real Azure calls)
- auto_approve_dev: Disabled by default (approvals required)
"""

import os
import warnings
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, model_validator

from .engine.modes import LoopMode, LoopBudget
from .contracts.request import RiskTier
from .contracts.governance import PiiMode, ContentSafetyMode


class EngineType(str, Enum):
    """Router engine type."""
    CLASSIC = "classic"
    MAF_PREVIEW = "maf_preview"


class RetrieverMode(str, Enum):
    """Retriever implementation to use."""
    AI_SEARCH = "ai_search"
    FOUNDRY_IQ = "foundry_iq"
    CONFLUENCE = "confluence"
    SHAREPOINT = "sharepoint"


class CORSConfig(BaseModel):
    """CORS configuration for API security.
    
    By default, no origins are allowed. Must be explicitly configured
    for production deployments.
    """
    allowed_origins: List[str] = Field(
        default_factory=list,
        description="List of allowed CORS origins. Empty = no CORS allowed."
    )
    allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    allowed_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "OPTIONS"],
        description="Allowed HTTP methods"
    )
    allowed_headers: List[str] = Field(
        default_factory=lambda: ["Content-Type", "Authorization", "X-Correlation-ID"],
        description="Allowed request headers"
    )

    def is_development_mode(self) -> bool:
        """Check if CORS is in development mode (wildcard allowed)."""
        return "*" in self.allowed_origins


class AISearchFieldConfig(BaseModel):
    """Field mapping configuration for Azure AI Search.
    
    Maps index field names to expected content structure.
    """
    vector_field: str = Field(
        default="contentVector",
        description="Vector embedding field name"
    )
    content_field: str = Field(
        default="content",
        description="Main content field name"
    )
    title_field: str = Field(
        default="title",
        description="Title field name"
    )
    url_field: str = Field(
        default="url",
        description="Source URL field name"
    )
    id_field: str = Field(
        default="id",
        description="Document ID field name"
    )
    metadata_field: Optional[str] = Field(
        default="metadata",
        description="Optional metadata field name"
    )


class LogicAppConfig(BaseModel):
    """Configuration for a Logic App tool."""
    name: str = Field(..., description="Tool name")
    endpoint_url: str = Field(..., description="Logic App HTTP trigger URL")
    requires_approval: bool = Field(
        default=True,  # Changed to True for production safety
        description="Whether this tool requires human approval"
    )
    timeout_ms: int = Field(
        default=30000,
        description="Execution timeout in milliseconds"
    )
    schema_version: str = Field(
        default="v1",
        description="Tool schema version for validation"
    )


class WorkflowConfig(BaseModel):
    """Workflow configuration from agent.yaml.

    Controls loop mode selection and router behavior.
    """
    default_mode: LoopMode = Field(
        default=LoopMode.PLAN_RAG,
        description="Default loop mode for this agent"
    )
    allowed_modes: List[LoopMode] = Field(
        default_factory=lambda: [LoopMode.FAST_RAG, LoopMode.PLAN_RAG],
        description="List of allowed loop modes"
    )
    router_can_override: bool = Field(
        default=True,
        description="Whether router can override default mode based on query"
    )
    planning_enabled: bool = Field(
        default=True,
        description="Enable query planning step"
    )
    critic_enabled: bool = Field(
        default=True,
        description="Enable critic/sufficiency loop"
    )


class KnowledgeConfig(BaseModel):
    """Configuration for knowledge retrieval.
    
    Supports multiple retriever types with field mapping configuration.
    mock_mode is controlled by environment for safe production defaults.
    """
    enabled: bool = Field(default=True, description="Enable knowledge retrieval")

    # Retriever selection
    mode: RetrieverMode = Field(
        default=RetrieverMode.AI_SEARCH,
        description="Retriever implementation"
    )

    # Mock mode: controlled by MOCK_MODE env var, defaults to False for production
    mock_mode: bool = Field(
        default_factory=lambda: os.environ.get("MOCK_MODE", "false").lower() == "true",
        description="Use mock retriever for development. Set MOCK_MODE=true to enable."
    )

    # Azure AI Search configuration
    search_endpoint: Optional[str] = Field(
        default=None,
        description="Azure AI Search endpoint URL"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Azure AI Search index name"
    )
    semantic_config: Optional[str] = Field(
        default=None,
        description="Semantic configuration name"
    )

    # Field mappings for AI Search
    field_config: AISearchFieldConfig = Field(
        default_factory=AISearchFieldConfig,
        description="Field name mappings for search index"
    )

    # Foundry IQ KB configuration
    kb_name: Optional[str] = Field(
        default=None,
        description="Foundry IQ Knowledge Base name"
    )

    # Search defaults
    default_top_k: int = Field(default=5, description="Default results to retrieve")
    use_semantic_reranking: bool = Field(
        default=True,
        description="Enable semantic reranking"
    )


class GovernanceConfig(BaseModel):
    """Configuration for governance and guardrails."""
    pii_mode: PiiMode = Field(
        default=PiiMode.DETECT,
        description="PII handling mode"
    )
    content_safety_mode: ContentSafetyMode = Field(
        default=ContentSafetyMode.STANDARD,
        description="Content safety check level"
    )
    policy_set_id: Optional[str] = Field(
        default=None,
        description="Custom policy set to apply"
    )


class AgentConfig(BaseModel):
    """Complete agent configuration.

    Supports both legacy project_connection_string and new project_endpoint
    patterns for Azure AI Foundry SDK compatibility.
    """

    # Agent identity
    name: str = Field(default="enterprise_agent", description="Agent name")
    version: str = Field(default="1.0.0", description="Agent version")

    # Azure AI Foundry connection (new SDK pattern)
    project_endpoint: Optional[str] = Field(
        default=None,
        description="Azure AI Foundry project endpoint (preferred)"
    )

    # Legacy connection string (for backwards compatibility)
    project_connection_string: Optional[str] = Field(
        default=None,
        description="Azure AI Foundry project connection string (legacy)"
    )

    # Model configuration
    model_deployment: str = Field(
        default="gpt-4o",
        description="Azure OpenAI deployment name"
    )

    # Router configuration
    orchestrator_mode: EngineType = Field(
        default=EngineType.CLASSIC,
        description="Router engine type"
    )

    # Loop configuration (legacy - prefer workflow config)
    loop_mode: LoopMode = Field(
        default=LoopMode.PLAN_RAG,
        description="Default loop mode for this agent (legacy, use workflow.default_mode)"
    )
    budget: LoopBudget = Field(
        default_factory=LoopBudget,
        description="Resource budget for the loop"
    )

    # Workflow configuration (new structured config)
    workflow: WorkflowConfig = Field(
        default_factory=WorkflowConfig,
        description="Workflow configuration with allowed modes and settings"
    )

    # Risk tier
    risk_tier: RiskTier = Field(
        default=RiskTier.TIER2,
        description="Default risk tier for this agent"
    )

    # Knowledge retrieval
    knowledge: KnowledgeConfig = Field(
        default_factory=KnowledgeConfig,
        description="Knowledge retrieval configuration"
    )

    # Tool configuration
    logic_apps: List[LogicAppConfig] = Field(
        default_factory=list,
        description="Logic App tools available to this agent"
    )
    tools_allowed: List[str] = Field(
        default_factory=list,
        description="List of allowed tool names"
    )

    # Governance
    governance: GovernanceConfig = Field(
        default_factory=GovernanceConfig,
        description="Governance and guardrails configuration"
    )

    # CORS Configuration
    cors: CORSConfig = Field(
        default_factory=CORSConfig,
        description="CORS configuration for API security"
    )

    # APIM Configuration (for rate limiting, auth)
    apim_base_url: Optional[str] = Field(
        default=None,
        description="Azure API Management base URL"
    )
    apim_api_key: Optional[str] = Field(
        default=None,
        description="APIM API subscription key (from env: APIM_API_KEY)"
    )

    # Tool approval configuration
    auto_approve_dev: bool = Field(
        default_factory=lambda: os.environ.get("ENV", "production") == "development",
        description="Auto-approve tool calls in development. Set ENV=development to enable."
    )
    tools_no_approval: List[str] = Field(
        default_factory=list,
        description="Tool names that never require approval (e.g., add_comment)"
    )

    # Feature flags
    enable_maf_router: bool = Field(
        default=False,
        description="Enable MAF router (preview)"
    )

    # Prompt configuration
    prompt_pack: str = Field(
        default="standard",
        description="Prompt pack to use (standard or custom)"
    )
    prompts_dir: Optional[str] = Field(
        default=None,
        description="Path to custom prompts directory"
    )
    custom_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom prompt overrides"
    )

    @model_validator(mode='after')
    def validate_azure_connection(self) -> 'AgentConfig':
        """Validate Azure AI Foundry connection settings.

        Requires either project_endpoint (preferred) or project_connection_string.
        Emits deprecation warning if only connection_string is provided.
        """
        has_endpoint = bool(self.project_endpoint)
        has_connection_string = bool(self.project_connection_string)

        # Allow both to be None for local development/testing
        # In production, at least one should be set
        if has_connection_string and not has_endpoint:
            warnings.warn(
                "project_connection_string is deprecated. "
                "Use project_endpoint instead for Azure AI Foundry connection.",
                DeprecationWarning,
                stacklevel=2,
            )

        return self

    def get_project_endpoint(self) -> Optional[str]:
        """Get the project endpoint, preferring project_endpoint over connection_string.

        Returns:
            Project endpoint URL or None if not configured
        """
        return self.project_endpoint or self.project_connection_string


def load_config_from_yaml(path: str) -> AgentConfig:
    """Load agent configuration from a YAML file.

    Supports:
    - Environment variable expansion: ${VAR_NAME} or ${VAR_NAME:-default}
    - Nested config normalization from agent.yaml structure
    - Backward compatibility with legacy field names

    Args:
        path: Path to agent.yaml file

    Returns:
        AgentConfig populated from the YAML
    """
    import re
    import yaml

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    # Environment variable expansion with default value support
    # Supports ${VAR} and ${VAR:-default}
    env_pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def expand_env(value):
        if not isinstance(value, str):
            return value
        
        def replacer(match):
            env_var = match.group(1)
            default = match.group(2) if match.group(2) is not None else match.group(0)
            return os.environ.get(env_var, default)
        
        return env_pattern.sub(replacer, value)

    def expand_dict(d):
        if isinstance(d, dict):
            return {k: expand_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [expand_dict(v) for v in d]
        else:
            return expand_env(d)

    expanded = expand_dict(raw)

    # Normalize nested structures from agent.yaml
    normalized = _normalize_config(expanded)
    
    return AgentConfig(**normalized)


def _normalize_config(raw: Dict) -> Dict:
    """Normalize agent.yaml structure to AgentConfig fields.
    
    Handles:
    - project.* -> top-level fields
    - workflow.* -> workflow config
    - retrieval.* -> knowledge config
    - tools.* -> tool configuration
    - guardrails.* -> governance config
    """
    result = {}
    
    # Extract top-level project settings
    project = raw.get("project", {})
    result["name"] = project.get("name", raw.get("name"))
    result["version"] = project.get("version", raw.get("version"))
    result["project_endpoint"] = project.get("project_endpoint", raw.get("project_endpoint"))
    result["model_deployment"] = project.get("model_deployment", raw.get("model_deployment"))
    
    # Workflow config
    workflow_raw = raw.get("workflow", {})
    if workflow_raw:
        # Normalize mode values to lowercase (enum expects lowercase)
        default_mode = workflow_raw.get("default_mode")
        if isinstance(default_mode, str):
            default_mode = default_mode.lower()
        
        allowed_modes = workflow_raw.get("allowed_modes")
        if isinstance(allowed_modes, list):
            allowed_modes = [m.lower() if isinstance(m, str) else m for m in allowed_modes]
        
        result["workflow"] = {
            "default_mode": default_mode,
            "allowed_modes": allowed_modes,
            "router_can_override": workflow_raw.get("router", {}).get("router_can_override", True),
            "planning_enabled": workflow_raw.get("planning", {}).get("enabled", True),
            "critic_enabled": workflow_raw.get("critic", {}).get("enabled", True),
        }
        # Remove None values
        result["workflow"] = {k: v for k, v in result["workflow"].items() if v is not None}
    
    # Budget from workflow
    budget_raw = workflow_raw.get("budget", {})
    if budget_raw:
        result["budget"] = budget_raw
    
    # Knowledge/retrieval config
    retrieval_raw = raw.get("retrieval", {})
    if retrieval_raw:
        ai_search = retrieval_raw.get("ai_search", {})
        result["knowledge"] = {
            "enabled": retrieval_raw.get("enabled", True),
            "mode": retrieval_raw.get("type", "ai_search"),
            "search_endpoint": ai_search.get("endpoint", retrieval_raw.get("endpoint")),
            "index_name": ai_search.get("index_name"),
            "semantic_config": ai_search.get("semantic_config"),
            "default_top_k": ai_search.get("default_top_k", 5),
            "use_semantic_reranking": ai_search.get("use_semantic_reranking", True),
            "kb_name": retrieval_raw.get("foundry_iq", {}).get("kb_name"),
        }
        # Field config if present
        if any(k in ai_search for k in ["vector_field", "content_field", "title_field", "url_field"]):
            result["knowledge"]["field_config"] = {
                "vector_field": ai_search.get("vector_field", "contentVector"),
                "content_field": ai_search.get("content_field", "content"),
                "title_field": ai_search.get("title_field", "title"),
                "url_field": ai_search.get("url_field", "url"),
            }
        result["knowledge"] = {k: v for k, v in result["knowledge"].items() if v is not None}
    
    # Tools config
    tools_raw = raw.get("tools", {})
    if tools_raw:
        result["tools_allowed"] = tools_raw.get("allowlist", [])
        result["tools_no_approval"] = tools_raw.get("approvals", {}).get("allowlist_no_approval", [])
        
        # Logic Apps
        logic_apps_raw = tools_raw.get("logic_apps", [])
        if logic_apps_raw:
            result["logic_apps"] = logic_apps_raw
    
    # Guardrails -> governance
    guardrails_raw = raw.get("guardrails", {})
    if guardrails_raw:
        result["governance"] = {
            "pii_mode": guardrails_raw.get("pii_mode", "detect"),
            "content_safety_mode": guardrails_raw.get("content_safety_mode", "standard"),
        }
    
    # Prompts config
    prompts_raw = raw.get("prompts", {})
    if prompts_raw:
        result["prompt_pack"] = prompts_raw.get("pack", "standard")
    
    # CORS config if present
    cors_raw = raw.get("cors", {})
    if cors_raw:
        result["cors"] = cors_raw
    
    # Router mode
    router_mode = workflow_raw.get("router", {}).get("mode")
    if router_mode == "maf":
        result["enable_maf_router"] = True
    
    # Remove None values from top level
    result = {k: v for k, v in result.items() if v is not None}
    
    return result
