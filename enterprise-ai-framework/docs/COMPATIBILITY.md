# Compatibility Matrix

## Python Version

| Python | Status |
|--------|--------|
| 3.10 | ✅ Tested |
| 3.11 | ✅ Tested |
| 3.12 | ✅ Tested |
| 3.13 | ✅ Tested |

## Azure SDK Versions

| Package | Version | Notes |
|---------|---------|-------|
| `azure-identity` | >=1.15.0 | Required |
| `azure-search-documents` | >=11.4.0 | For AI Search retrieval |
| `azure-ai-projects` | >=1.0.0b1 | For Foundry SDK (preview) |
| `azure-monitor-opentelemetry-exporter` | >=1.0.0b21 | Optional, for tracing |

## OpenTelemetry Versions

| Package | Version |
|---------|---------|
| `opentelemetry-api` | >=1.21.0 |
| `opentelemetry-sdk` | >=1.21.0 |
| `opentelemetry-exporter-otlp` | >=1.21.0 |

## Framework Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| `pydantic` | >=2.0.0 | Required |
| `fastapi` | >=0.100.0 | Required |
| `uvicorn` | >=0.23.0 | Required |
| `aiohttp` | >=3.8.0 | For async HTTP |
| `tenacity` | >=8.2.0 | For retries |
| `pyyaml` | >=6.0 | For config loading |

## Preview Dependencies

> ⚠️ Preview packages must be pinned exactly

| Package | Pinned Version | Status |
|---------|----------------|--------|
| `azure-ai-projects` | 1.0.0b1 | Preview |
| `azure-ai-inference` | 1.0.0b1 | Preview |

## Azure AI Foundry

| Feature | Status | Notes |
|---------|--------|-------|
| Project connection | ✅ Supported | Via `PROJECT_ENDPOINT` |
| Model deployment | ✅ Supported | GPT-4o, GPT-4, GPT-3.5-Turbo |
| Knowledge Base (IQ) | 🚧 Placeholder | Raises `NotImplementedError` |
| Tracing export | ✅ Supported | Via Azure Monitor |

## Azure Container Apps

| Feature | Status |
|---------|--------|
| OIDC authentication | ✅ Configured |
| Secrets via secretref | ✅ Configured |
| Health probes | ✅ Implemented |
| Environment variables | ✅ Implemented |

## Known Issues

1. **Pydantic V2 Warning**: `LoopBudget` uses deprecated class-based config
   - Workaround: Will be fixed in next release

2. **Foundry IQ Not Implemented**: `foundry_iq` retriever raises error
   - Workaround: Use `ai_search` retriever

3. **Sync AI Search**: SearchClient is sync within async method
   - Workaround: Use `MOCK_MODE=true` for high concurrency testing
