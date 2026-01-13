# Observability Specification

## Tracing

The framework uses OpenTelemetry for distributed tracing.

### Span Names

| Span | Description |
|------|-------------|
| `agent.handle` | Root span for request processing |
| `agent.route` | Router decision making |
| `agent.plan` | Query planning and decomposition |
| `agent.retrieve` | Content retrieval from data sources |
| `agent.critic` | Sufficiency evaluation |
| `agent.synthesize` | Response generation |
| `agent.tool_call.<tool>` | Tool execution |

### Required Span Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `correlation_id` | string | Request correlation ID |
| `thread_id` | string | Conversation thread ID |
| `agent_name` | string | Agent configuration name |
| `loop_mode` | string | Selected loop mode |
| `iteration` | int | Current iteration (for critic loop) |
| `hit_count` | int | Number of retrieved chunks |
| `source` | string | Retrieval source identifier |
| `tool_name` | string | Name of executed tool |
| `tool_status` | string | Tool execution status |

### Exporter Configuration

Set `TRACING_EXPORTER` environment variable:

| Value | Exporter | Additional Config |
|-------|----------|-------------------|
| `azure_monitor` | Azure Monitor | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| `otlp` | OTLP/gRPC | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| `console` | Console (dev) | None |
| `none` | Disabled | None |

### Example: Azure Monitor

```bash
export TRACING_EXPORTER=azure_monitor
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."
```

## Logging

Structured logging with the following levels:

- `DEBUG`: Detailed flow information
- `INFO`: Request processing, mode decisions
- `WARNING`: Non-fatal issues, fallbacks
- `ERROR`: Failed operations, exceptions

### Log Fields

All log entries include:
- `correlation_id`
- `thread_id`
- `agent_name`
- Timestamp (ISO 8601)

## Metrics (Future)

Planned metrics:
- `agent.requests.total` - Request count by mode, status
- `agent.latency.ms` - Processing time histogram
- `agent.retrieval.hits` - Chunks retrieved per request
- `agent.tools.executed` - Tool executions by name, status

## Audit Trail

Every response includes `AuditFields`:

```json
{
  "audit": {
    "correlation_id": "uuid",
    "thread_id": "thread-id",
    "request_id": "req-id",
    "agent_name": "confluence-bot",
    "loop_mode": "plan_rag",
    "iterations_used": 1,
    "data_sources_used": ["azure_ai_search"],
    "tools_called": [],
    "risk_tier": "tier2"
  }
}
```
