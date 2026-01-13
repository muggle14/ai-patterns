# Operations Runbook

## Deployment

### Prerequisites

1. Azure Container Registry (ACR) access
2. Azure Container Apps environment
3. GitHub Actions OIDC configured
4. Secrets configured in ACA

### Deploy via GitHub Actions

1. Push to `main` branch for production
2. Push to `develop` branch for dev
3. Manual deploy: Actions > "Deploy Enterprise Agent" > Run workflow

### Manual Deploy

```bash
# Build image
docker build -f use-cases/confluence-bot/Dockerfile -t myacr.azurecr.io/confluence-bot:latest .

# Push to ACR
docker push myacr.azurecr.io/confluence-bot:latest

# Deploy to ACA
az containerapp update \
  --name aca-confluence-bot-dev \
  --resource-group my-rg \
  --image myacr.azurecr.io/confluence-bot:latest
```

## Health Checks

### Liveness Probe
```bash
curl https://aca-confluence-bot-dev.azurecontainerapps.io/healthz
# Expected: {"status": "healthy", "version": "1.0.0"}
```

### Readiness Probe
```bash
curl https://aca-confluence-bot-dev.azurecontainerapps.io/readyz
# Expected: {"status": "ready", "checks": {"engine": "ok", "config": "ok"}}
```

## Common Issues

### Issue: "Engine not initialized"
**Symptom**: 503 error on `/chat`, `/readyz` shows `engine: not_initialized`

**Causes**:
1. Missing `PROJECT_ENDPOINT` environment variable
2. Invalid `agent.yaml` configuration
3. Dependency import error

**Resolution**:
1. Check container logs: `az containerapp logs show ...`
2. Verify environment variables are set
3. Test locally with same config

### Issue: "No CORS origins configured"
**Symptom**: Browser requests blocked, warning in logs

**Cause**: Missing `cors.allowed_origins` in config

**Resolution**: Add CORS config to `agent.yaml`:
```yaml
cors:
  allowed_origins:
    - https://your-frontend.azurewebsites.net
```

### Issue: Validation errors on startup
**Symptom**: Pydantic validation errors in logs

**Cause**: Incorrect config format or missing required fields

**Resolution**:
1. Check field names match expected schema
2. Ensure enums use lowercase values (`plan_rag` not `PLAN_RAG`)
3. Verify environment variable substitution works

## Scaling

### Horizontal Scaling
ACA handles auto-scaling. Configure:
```yaml
scale:
  minReplicas: 1
  maxReplicas: 10
  rules:
    - name: http-requests
      type: custom
      metadata:
        type: http
        metadata:
          concurrentRequests: 50
```

### Performance Tuning
- Decrease `default_top_k` for faster retrieval
- Use `fast_rag` mode for simple queries
- Enable caching at APIM layer

## Monitoring

### Key Metrics
- Request latency (p50, p95, p99)
- Error rate by mode
- Retrieval hit count
- Tool execution status

### Alerts
Configure for:
- Error rate > 5%
- P99 latency > 10s
- Health check failures

## Rollback

```bash
# Get previous revision
az containerapp revision list \
  --name aca-confluence-bot-dev \
  --resource-group my-rg

# Rollback to previous revision
az containerapp revision set-mode \
  --name aca-confluence-bot-dev \
  --resource-group my-rg \
  --mode single

az containerapp ingress traffic set \
  --name aca-confluence-bot-dev \
  --resource-group my-rg \
  --revision-weight <old-revision>=100
```
