# Security and Governance

## Security Principles

1. **Least Privilege**: Agents only access configured data sources
2. **Secure Defaults**: No wildcards, approvals required, mock mode off
3. **Audit Trail**: All actions logged with correlation IDs
4. **Secrets Management**: No secrets in code or config files

## CORS Security

By default, no CORS origins are allowed. Configure explicitly:

```yaml
cors:
  allowed_origins:
    - https://myapp.azurewebsites.net
  allow_credentials: true
  allowed_methods: [GET, POST, OPTIONS]
  allowed_headers: [Content-Type, Authorization, X-Correlation-ID]
```

> ⚠️ Never use `"*"` in production

## Secrets Management

Use environment variables for all secrets:

| Secret | Environment Variable |
|--------|---------------------|
| Foundry endpoint | `PROJECT_ENDPOINT` |
| Search endpoint | `SEARCH_ENDPOINT` |
| Logic App URL | `LOGIC_APP_*` |
| APIM key | `APIM_API_KEY` |

In Azure Container Apps, use secretref:
```yaml
environmentVariables:
  PROJECT_ENDPOINT=secretref:project-endpoint
```

## PII Handling

Configure `guardrails.pii_mode`:

| Mode | Behavior |
|------|----------|
| `off` | No PII handling (not recommended) |
| `detect` | Log detected PII, continue processing |
| `redact` | Redact PII before processing |

**Note**: PII detection hooks are defined but not fully implemented. Plan for external PII service integration.

## Content Safety

Configure `guardrails.content_safety_mode`:

| Mode | Behavior |
|------|----------|
| `off` | No content filtering |
| `standard` | Block clearly harmful content |
| `strict` | Block harmful + borderline content |

## Tool Execution Safety

### Approval Requirements

Tools require approval by default. Configure exceptions:

```yaml
tools:
  approvals:
    default_required: true
    allowlist_no_approval:
      - add_comment  # Low-risk actions
```

### Idempotency

All tool calls include an idempotency key:
```
{thread_id}:{tool_name}:{payload_hash}
```

This prevents duplicate executions from retries.

### Payload Validation

Tool payloads are validated against Pydantic schemas before execution.

## Risk Tiers

| Tier | Description | Controls |
|------|-------------|----------|
| Tier 1 | Internal, low sensitivity | Basic audit |
| Tier 2 | Internal, moderate sensitivity | PII detection, approval for actions |
| Tier 3 | External or high sensitivity | Full governance, strict content safety |

## Audit Requirements

All requests must include:
- `correlation_id`: For distributed tracing
- `thread_id`: For conversation context
- `request_id`: For deduplication

All responses include full audit trail in `response.audit`.
