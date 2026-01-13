# Foundry Integration

## Azure AI Foundry SDK

The framework uses `PROJECT_ENDPOINT` as the primary connection method:

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
```

## Connection Methods

| Method | Config | Status |
|--------|--------|--------|
| Project Endpoint | `project_endpoint` | ✅ Recommended |
| Connection String | `project_connection_string` | ⚠️ Deprecated |

## Model Access

Models are accessed via deployment name:

```yaml
project:
  model_deployment: gpt-4o
```

Supported deployments:
- `gpt-4o` (recommended)
- `gpt-4-turbo`
- `gpt-35-turbo`

### APIM Routing

For enterprise deployments, route through Azure API Management:

```yaml
apim_base_url: https://apim.contoso.com/azure-openai
apim_api_key: ${APIM_API_KEY}
```

## Foundry IQ (Knowledge Base)

> 🚧 **Not Yet Implemented**

Foundry IQ provides managed Knowledge Bases with:
- Built-in query planning
- Automatic citations
- Managed vector storage

Current status: `FoundryIQRetriever` raises `NotImplementedError`.

### Future Integration

```yaml
retrieval:
  type: foundry_iq
  foundry_iq:
    kb_name: kb-confluence
```

## Tracing Integration

Export traces to Azure Monitor (Application Insights):

```bash
export TRACING_EXPORTER=azure_monitor
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."
```

Traces appear in Application Insights > Transaction Search with:
- Operation name: `agent.handle`
- Custom dimensions: `correlation_id`, `loop_mode`, etc.

## Agent SDK Integration (Future)

The Foundry Agent SDK can be used for:
- Atomic agents as specialized skills
- Tool execution with built-in tracing
- Thread management

This is tracked as P2 work in `AtomicAgentCapability`.
