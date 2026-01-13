# Configuration Reference

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROJECT_ENDPOINT` | Yes* | - | Azure AI Foundry project endpoint |
| `SEARCH_ENDPOINT` | Yes* | - | Azure AI Search endpoint |
| `MOCK_MODE` | No | `false` | Use mock retrievers for development |
| `ENV` | No | `production` | Environment name (`development`, `staging`, `production`) |
| `TRACING_EXPORTER` | No | `none` | Trace exporter (`azure_monitor`, `otlp`, `console`, `none`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | - | App Insights connection for azure_monitor exporter |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | - | OTLP collector endpoint |
| `APIM_BASE_URL` | No | - | Azure API Management base URL |
| `APIM_API_KEY` | No | - | APIM subscription key |

*Required unless `MOCK_MODE=true`

## agent.yaml Structure

```yaml
# Project identity
project:
  name: my-bot
  version: 1.0.0
  project_endpoint: ${PROJECT_ENDPOINT}
  model_deployment: gpt-4o

# Workflow configuration
workflow:
  default_mode: plan_rag          # fast_rag | plan_rag | full_actor_critic | action_gated
  allowed_modes: [fast_rag, plan_rag, full_actor_critic]
  
  router:
    mode: classic                 # classic | maf
    router_can_override: true     # Allow router to select different mode
  
  budget:
    max_iterations: 2             # Max critic loop iterations
    max_latency_ms: 8000          # Max total processing time
    max_prompt_tokens: 4000       # Token limit for prompts
    max_output_tokens: 2000       # Token limit for responses
  
  planning:
    enabled: true
  
  critic:
    enabled: true
    confidence_threshold: 0.72    # Minimum confidence for sufficiency

# Retrieval configuration
retrieval:
  enabled: true
  type: ai_search                 # ai_search | foundry_iq
  
  ai_search:
    endpoint: ${SEARCH_ENDPOINT}
    index_name: idx-mybot
    semantic_config: semantic-mybot
    default_top_k: 5
    use_semantic_reranking: true
    vector_field: contentVector
    content_field: content
    title_field: title
    url_field: url
  
  foundry_iq:
    kb_name: kb-mybot             # Foundry KB name

# Guardrails
guardrails:
  pii_mode: detect                # off | detect | redact
  content_safety_mode: standard   # off | standard | strict

# Tools (for ACTION_GATED mode)
tools:
  enabled: true
  allowlist:
    - servicenow.create_incident
    - servicenow.add_comment
  
  approvals:
    default_required: true
    allowlist_no_approval:
      - servicenow.add_comment
  
  execution:
    default_timeout_ms: 30000
    retries: 2
  
  logic_apps:
    - name: servicenow.create_incident
      endpoint_url: ${LOGIC_APP_URL}
      requires_approval: true
      timeout_ms: 30000

# CORS (for browser clients)
cors:
  allowed_origins:
    - https://myapp.azurewebsites.net
  allow_credentials: true

# Prompts
prompts:
  pack: standard
  standard_pack_version: v1
  citation_required: true

# Audit
audit:
  risk_tier: Tier2
  required_fields:
    - correlation_id
    - thread_id
    - sources_used
```

## Loop Modes

### fast_rag
- **Steps**: Retrieve → Synthesize
- **Use case**: Simple questions, latency-sensitive
- **Skips**: Planning, Critic loop

### plan_rag
- **Steps**: Plan → Retrieve → Synthesize
- **Use case**: Standard Q&A requiring query decomposition
- **Skips**: Critic loop

### full_actor_critic
- **Steps**: Plan → Retrieve → Critic → (loop) → Synthesize
- **Use case**: Complex questions, quality-sensitive responses
- **Loops**: Until `confidence >= confidence_threshold` or `max_iterations`

### action_gated
- **Steps**: Full + Act (tool execution)
- **Use case**: Requests requiring side effects (create ticket, update record)
- **Safety**: Requires approval unless in `tools_no_approval` list

## Retriever Types

### ai_search
Direct Azure AI Search with:
- Semantic search with integrated vectorization
- Hybrid search (vector + keyword)
- Semantic reranking
- Configurable field mappings

### foundry_iq
Azure AI Foundry managed Knowledge Base:
- Built-in query planning
- Managed citations
- **Note**: Not yet implemented; raises `NotImplementedError`

## Governance Modes

### pii_mode
- `off`: No PII handling
- `detect`: Log PII detection, don't block
- `redact`: Redact PII before processing

### content_safety_mode
- `off`: No content safety checks
- `standard`: Block harmful content
- `strict`: Block harmful + borderline content
