# Developer Pathway

## Quick Start

### 1. Install the Framework

```bash
cd ai-patterns-core
pip install -e ".[dev]"
```

### 2. Run an Existing Bot

```bash
cd use-cases/confluence-bot
export PROJECT_ENDPOINT=your-foundry-endpoint
export SEARCH_ENDPOINT=your-search-endpoint
export MOCK_MODE=true  # Start with mocks

python main.py
```

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/healthz

# Send a query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-001",
    "thread_id": "thread-001",
    "user_query": "What is the vacation policy?"
  }'
```

## Creating a New Bot

### 1. Create Directory Structure

```
use-cases/my-bot/
├── agent.yaml      # Configuration
├── main.py         # Entry point
├── Dockerfile      # Container build
├── prompts/        # Custom prompts
│   └── __init__.py
└── requirements.txt
```

### 2. Configure agent.yaml

```yaml
project:
  name: my-bot
  version: 1.0.0
  project_endpoint: ${PROJECT_ENDPOINT}
  model_deployment: gpt-4o

workflow:
  default_mode: plan_rag
  allowed_modes: [fast_rag, plan_rag]

retrieval:
  type: ai_search
  ai_search:
    endpoint: ${SEARCH_ENDPOINT}
    index_name: idx-mybot
    semantic_config: semantic-mybot

guardrails:
  pii_mode: detect
  content_safety_mode: standard
```

### 3. Create main.py

```python
import os
from enterprise_agent_core.api import create_app
from enterprise_agent_core.config import load_config_from_yaml

config_path = os.path.join(os.path.dirname(__file__), "agent.yaml")
config = load_config_from_yaml(config_path)
app = create_app(config)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```

## Development Workflow

### Running Tests

```bash
cd ai-patterns-core
pytest tests/ -v
```

### Local Development with Mocks

Set these environment variables:
- `MOCK_MODE=true` - Use mock retrievers
- `ENV=development` - Enable auto-approve for tools
- `TRACING_EXPORTER=console` - Log spans to console

### Debugging

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `AgentConfig` | Pydantic model for all configuration |
| `AgentWorkflowEngine` | Core orchestrator for the cognitive loop |
| `RetrieverFactory` | Creates retrievers based on config/route |
| `RouteDecision` | Router output with mode and retriever selection |

## Next Steps

- Read [Config Reference](CONFIG_REFERENCE.md) for all options
- See [Pattern Playbook](PATTERN_PLAYBOOK.md) for architecture details
- Check [Runbook](RUNBOOK.md) for operational guidance
