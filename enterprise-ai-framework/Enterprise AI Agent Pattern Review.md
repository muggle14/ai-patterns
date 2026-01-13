# Enterprise AI Agent Pattern Review (Foundry + MAF)

This document is a **critical architectural review** of your “Reason → Plan → Retrieve → Sufficiency → Synthesize → (Optional) Act” framework, with a **hybrid Foundry SDK + Microsoft Agent Framework (MAF)** approach, focused on:

* **Fungibility** (swap components without rewrites)
* **Productionization** (security, operability, deployment, governance)
* **Standardization** (contracts, prompts, tracing, naming)
* **Preview-risk management** (MAF + any preview Foundry capabilities)

---

## 0) Executive snapshot

### What’s strong already

* You’re enforcing a **state machine** (the Cognitive Loop) rather than “LLM magic.”
* You’re explicitly separating **Patterns (core)** vs **Projects (use-case config)**.
* You’re thinking in **contracts** (schemas) and **tool boundaries**.
* You’ve already aligned to **Foundry tracing + OTel** and **ACA runtime**.

### Biggest architectural risks (in order)

1. **Orchestration fragmentation**: MAF + Foundry Agents + custom router can become three competing control planes unless you enforce a single “execution contract.”
2. **Missing contract boundaries**: today the contracts only cover ingestion + output; you need contracts for **planning, retrieval, sufficiency, tool invocation, and governance**.
3. **Thread + memory ambiguity**: thread_id exists, but you need consistent rules for **ownership**, **persistence**, **scope**, and **cross-agent transfer**.
4. **Observability gaps**: you’ll get traces, but not the **right spans + attributes** to debug retrieval quality, latency, and tool failures.
5. **Authorization/access trimming**: retrieval must enforce **per-user / group trimming** consistently across Confluence/SharePoint/Search.
6. **Latency**: forcing full actor-critic for every query will be too slow; you need “modes.”

### Recommended direction

**Use Foundry SDK Agents as the default stable execution substrate (“muscle”),** and treat MAF as an **optional orchestrator plugin (“brain”) behind an interface**, enabled per environment via config.

Key idea:

* **Patterns repo** exposes *interfaces + contracts + reference implementations*.
* **Projects repo** is *thin*, mostly config + tool wiring + deployment.

---

## 1) One decision to lock first: “Who owns orchestration?”

### You must pick exactly one **Source of Truth** for the loop

Pick one of these as the canonical state machine runner:

**Option A — Core Engine is yours (recommended):**

* Your Python `AgentWorkflowEngine` runs the state machine.
* Foundry Agents are invoked as **Atomic sub-agents** (skills).
* MAF can be used as a **router plugin** inside your engine.

**Option B — MAF owns the loop (higher preview risk):**

* MAF Workflow runs the loop.
* Your engine becomes a thin wrapper.
* Requires stronger version pinning + compatibility testing.

**Option C — Foundry “Agent tool + KB tool” owns the loop (lowest code, least control):**

* You let the hosted Agent decide planning/retrieval.
* You lose deterministic control over query planning / multi-hop.

### Recommended: Option A

Because it gives you:

* Deterministic step control (skip steps for latency)
* Clear contracts
* Freedom to swap orchestrator (Classic vs MAF) without changing atomic agents

---

## 2) Cognitive Loop standardization (the “Law”)

### 2.1 Define loop variants (“modes”) to manage latency

Not every use case needs all steps.

Define **LoopMode**:

* **FAST_RAG**: Retrieve → Synthesize (no planning, no critic)
* **PLAN_RAG**: Plan → Retrieve → Synthesize
* **FULL_ACTOR_CRITIC**: Plan → Retrieve → Critic → (Loop) → Synthesize
* **ACTION_GATED**: FULL + Human approval before Act

Rules:

* Default mode is **per project** (agent.yaml), but can be **auto-downgraded** based on SLAs.
* Enforce a **loop budget**: max_iterations, max_tokens, max_latency_ms.

### 2.2 Introduce a “Sufficiency Gate” contract

Instead of “boolean + reason” as prompt only, formalize:

* `SufficiencyResult { sufficient: bool, missing_aspects: [...], next_queries: [...], confidence: 0..1 }`

### 2.3 Add deterministic fallback

If critic returns insufficient twice:

* Switch to **broader retrieval** (increase top_k, expand query set)
* If still insufficient → return “I don’t know” with what was searched

---

## 3) Foundry SDK vs MAF: decision points and tagging

### 3.1 A practical decision matrix

Use **Foundry SDK Agents** when you need:

* Stable managed runtime for agent runs
* Standard tool execution patterns
* Deep integration with Foundry tracing and governance

Use **MAF** when you need:

* Multi-agent coordination patterns (group chat, routers, planners)
* Orchestration flexibility across many atomic agents

### 3.2 How to manage preview risk

Add a `preview_risk` tagging strategy:

* Tag modules (and config) with `stability: stable | preview | experimental`.
* Maintain a `COMPATIBILITY.md` with pinned versions and supported combinations.
* Always have a **ClassicRouter** fallback.

**Important SDK drift to plan for:** recent versions of the Foundry Projects SDK have **moved away from “project connection strings”** toward **project endpoints** as the primary connection mechanism. Treat this as a first-class compatibility concern (pin version where needed, but plan the migration path now).
Add a `preview_risk` tagging strategy:

* Tag modules (and config) with `stability: stable | preview | experimental`.
* Maintain a `COMPATIBILITY.md` with pinned versions and supported combinations.
* Always have a **ClassicRouter** fallback.

### 3.3 The “Proxy / Adapter” boundary you already started

You already have `AzureAtomicAdapter`. Make it the **only** way orchestration talks to Foundry Agents.

**Contract goal:** Your engine should not depend on SDK-specific “tool submit” mechanics.

---

## 4) Contracts: what you have, and what you must add

### 4.1 Fix existing contract hygiene (code-level)

In `contracts.py`:

* Replace mutable defaults (`{}` / `[]`) with `Field(default_factory=...)`.
* Add `schema_version`, `correlation_id`, and `timestamp` fields.

### 4.2 Add the missing contracts (minimum viable set)

Add these Pydantic models:

#### A) Planning

* `QueryPlan`: decomposed sub-questions, search intents, filters, required sources
* `QuerySpec`: per sub-query search parameters (top_k, semantic, vector_fields, filters, facets)

#### B) Retrieval

* `RetrievedChunk`: id, title, url, chunk_text, score, source_system, metadata
* `RetrievalResult`: chunks + metrics (latency, counts, recall hints)

#### C) Sufficiency / Critic

* `SufficiencyResult`: sufficient, confidence, gaps, next_query_specs

#### D) Tool execution

* `ToolCallRequest`: tool_name, input_schema_version, payload, idempotency_key
* `ToolCallResult`: status, outputs, error, retry_after

#### E) Governance / Guardrails

* `GovernanceRequest`: policy_id, pii_mode, content_safety_mode
* `GovernanceResult`: pii_redacted, blocks, severity, rationale

#### F) Final response

Extend `AgentResponse`:

* `response_mode` (FAST_RAG / FULL)
* `plan_summary` (optional)
* `retrieval_metrics`
* `governance_result` (structured)

### 4.3 Contracts must carry **trace context**

Add an optional `trace_context` field:

* W3C `traceparent` and `tracestate` propagation enables end-to-end traces across:

  * Router → Foundry Agents → Logic Apps → downstream systems

---

## 5) Retrieval factory: designing for Confluence, SharePoint, ServiceNow

### 5.1 Retrieval should be a pluggable strategy

Define:

* `IRetriever.retrieve(plan: QueryPlan, ctx: AgentContext) -> RetrievalResult`

Implementations:

* `FoundryIQKnowledgeBaseRetriever` (MCP tool / KB endpoint)
* `AISearchDirectRetriever` (SearchClient, your own query planning)
* `SharePointGraphRetriever` (Graph API + optional indexing)
* `ConfluenceRetriever` (Confluence API + optional indexing)

### 5.2 Use Foundry IQ KB when it buys you “agentic retrieval”

If Foundry IQ KB already does:

* query planning
* subqueries
* citations
  Then your local Planner should detect `retrieval_mode=managed` and **skip** duplicate work.

### 5.3 Filters, facets, access trimming

Standardize the filter strategy:

* `access_groups` and/or `user_oid` stored per chunk
* Retrieval layer always applies:

  * `filter = (access_groups contains any user_group)`

Also support:

* facets (doc_type, space, policy_area)
* structured metadata filters (date ranges, version, owner)

### 5.4 Versioned document comparisons (contracts use case)

For “contract v1 vs v2”:

* Represent “document set” queries explicitly in `QueryPlan`:

  * `compare: {left_doc_id, right_doc_id, sections:[...]}`
* Retrieval should return **paired chunks** with stable ids.

---

## 6) Prompts: what is standardized vs project-specific

### 6.1 Make prompt packs a first-class artifact

Structure:

* `prompts/standard/critic_sufficiency_v1.txt`
* `prompts/standard/citation_format_v1.txt`
* `prompts/project/hr/answer_style.txt`

### 6.2 Standard prompts must be versioned and tested

* `critic_sufficiency_v1` is global (pattern repo)
* `project_prompt_overrides` are per project

### 6.3 Prompt governance

* Record prompt version + hash in traces and in `AgentResponse`
* Run regression evals when changing standard prompts

---

## 7) Threading & memory: make it explicit

### 7.1 Thread ownership

Decide:

* **Foundry thread_id is canonical** (recommended), and is passed everywhere.

### 7.2 Memory scopes

Define:

* **Conversation memory**: per thread (short-lived)
* **User memory**: per user (opt-in, redaction, policy)
* **Org memory**: curated knowledge (not conversational)

### 7.3 Cross-agent memory transfer

When router calls multiple atomic agents:

* Use a shared `thread_id`
* Or maintain `subthread_ids` but propagate a `parent_thread_id`

---

## 8) Guardrails / PII redaction placement

### 8.1 Two-stage guardrail is the practical default

* **Stage A (Input guardrail)**: redact/label before retrieval to prevent leaking sensitive queries to external sources.
* **Stage B (Output guardrail)**: redact/validate final answer + tool payloads.

### 8.2 Tool payload redaction is non-negotiable

Before calling Logic Apps / ServiceNow:

* run a tool-payload scrub
* add an `idempotency_key`

### 8.3 Policy-driven config

Expose in agent.yaml:

* `pii_mode: off | detect | redact`
* `content_safety: off | standard | strict`

---

## 9) Observability: make traces actually useful

### 9.1 Minimum span model

Create spans for:

* `plan`
* `retrieve`
* `critic`
* `synthesize`
* `tool_call.{tool_name}`

### 9.2 Required attributes

On each span:

* `thread_id`
* `correlation_id`
* `agent_name`
* `project_name`
* `prompt_version`
* `retrieval.top_k`, `retrieval.filters_applied`, `retrieval.source`

### 9.3 Metrics that matter

* latency per step
* retrieval hit rate
* critic loop count
* tool error rate
* citations per answer

---

## 10) Deployment standardization for Azure Container Apps

### 10.1 Naming convention

Adopt something like:

* `aca-{domain}-{capability}-{env}`
* `acr-{org}-{env}`
* `mi-{domain}-{capability}-{env}`

### 10.2 A reusable ACA module

Standardize:

* container image naming
* env vars + secrets
* managed identity
* scaling rules
* health probes

### 10.3 CI/CD baseline (what’s missing today)

Your deploy.yaml is a skeleton. Add:

* azure login (OIDC)
* ACR push auth
* resource group + environment
* config injection for secrets

---

## 11) Repo split: Patterns vs Projects

### 11.1 Keep two repos, but enforce release discipline

Patterns repo:

* publishes `enterprise_agent_core==X.Y.Z`
* contains contracts, interfaces, standard prompts, reference implementations

Projects repo:

* pins pattern version
* contains agent.yaml + deployment + use-case glue

### 11.2 Compatibility matrix

Maintain in patterns repo:

* Foundry SDK version compatibility
* MAF preview version compatibility
* Breaking change log

---

## 12) Code review: structured feedback by file (from your zip)

### 12.1 `contracts.py`

**Issues**

* Mutable defaults (`{}` / `[]`) can leak state between instances.
* Output schema too thin for observability/governance.

**Fix now**

* Use `Field(default_factory=dict/list)`.
* Add `schema_version`, `correlation_id`, `timestamp`.

**Next**

* Introduce missing contracts: QueryPlan, RetrievalResult, SufficiencyResult, ToolCallResult, GovernanceResult.

---

### 12.2 `knowledge/connector.py`

**Issues**

* Missing `List` import → runtime error.
* No access trimming filters.
* Client created per call; no retries/timeouts.

**Fix now**

* Add typing imports.
* Add retry + timeout (tenacity).
* Add optional `filter` param and thread/user context.

**Next**

* Separate “SearchQuerySpec” from connector; connector should be dumb I/O.

---

### 12.3 `tools/foundry_search.py`

**Issues**

* Tool schema too minimal: no top_k, filters, facets.
* Returns JSON string of citations; better to return structured.

**Fix now**

* Expand schema: `query`, `top_k`, `filters`, `facets`, `mode`.

**Next**

* Align returned objects to `RetrievedChunk` contract.

---

### 12.4 `tools/logic_app.py`

**Issues**

* No error handling, no timeouts, no auth headers.
* No idempotency, no trace/correlation.

**Fix now**

* Add timeout, status check, retry policy.
* Add headers injection (managed identity token or key).

**Next**

* Enforce tool payload schema validation + redaction.

---

### 12.5 `tools/registry.py`

**Issues**

* Class-level `_tools` is effectively global state.

**Fix now**

* Make ToolRegistry an instance.

**Next**

* Provide `execute(tool_name, payload)` wrapper to centralize policy, redaction, tracing.

---

### 12.6 `atomic/adapter.py`

**Issues**

* Tool execution loop omitted; Foundry agent runs may require tool output submission.
* Message retrieval assumes ordering.

**Fix now**

* Implement tool-call handling (requires_action → execute tool → submit outputs).
* Fetch latest assistant message reliably.

**Next**

* Add streaming support and partial results.

---

### 12.7 `engine/factory.py`

**Issues**

* Bad relative import (`...atomic.adapter`).
* Uses sync DefaultAzureCredential with aio client.
* Agent IDs hardcoded.
* Uses `project_connection_string` (but newer SDKs are moving to `PROJECT_ENDPOINT` patterns).

**Fix now**

* Fix imports.
* Use async credential or consistent credential strategy.
* Load agent IDs from config.
* Add support for `project_endpoint` in config and route accordingly.

---

### 12.8 `engine/routers/classic.py`

**Issues**

* `actions_taken` uses dicts; should be `ActionLog` objects.
* No citations or metrics in response.

**Fix now**

* Populate `ActionLog` and include minimal retrieval metrics.

---

### 12.9 `engine/routers/maf_preview.py`

**Issues**

* Stub. No contract enforcement.

**Fix now**

* Implement behind `IEnterpriseRouter` while keeping fallback.

---

### 12.10 `use-cases/hr-bot/Dockerfile`

**Issues**

* References `requirements.txt` and `src.app:app` not present in the zip.

**Fix now**

* Add a minimal FastAPI app or switch to a simpler entrypoint.

---

### 12.11 `.github/workflows/deploy.yaml`

**Issues**

* Missing azure login and ACR auth.
* No environment separation.

**Fix now**

* Add OIDC login.
* Parameterize container app name and environment.

---

## 13) Recommended implementation sequence (practical)

### Phase 1 — Stabilize foundations (must-have)

1. Fix code hygiene issues (imports, defaults, async creds).
2. Implement tool-call submission in `AzureAtomicAdapter`.
3. Implement contracts v1 (planning/retrieval/sufficiency/governance).
4. Add loop modes + loop budget.

### Phase 2 — Retrieval + access trimming

1. Retrieval factory interfaces.
2. Access trimming filter strategy.
3. Add facets/filters into QuerySpec.

### Phase 3 — Observability + guardrails

1. Span model + attributes.
2. Input/output/tool payload guardrails.

### Phase 4 — MAF plugin + governance hardening

1. Implement MAF router behind interface.
2. Add compatibility matrix + pinned versions.
3. Evals/regression gating for prompt changes.

---

## 14) How we review together (one-by-one)

When we walk this together, we should do it in this order:

1. Orchestration ownership decision (Section 1)
2. Loop modes + sufficiency gate (Section 2)
3. Contracts v1 scope (Section 4)
4. Retrieval factory + access trimming (Section 5)
5. Thread/memory model (Section 7)
6. Guardrails (Section 8)
7. Observability (Section 9)
8. Deployment standard (Section 10)
9. Repo release discipline (Section 11)
10. Code patch plan (Section 12/13)

---

# Implementation Specs (Hand-off to a Coding Agent)

This section is a **build spec** you can give to an AI coding agent (or a developer) to implement Option A: **your own Python AgentWorkflowEngine** as the source-of-truth state machine, with **Foundry Agents as atomic skills** and **MAF as an optional router plugin**.

## A) Goals and non-goals

### Goals

* Enforce the enterprise “Cognitive Loop”: **Plan → Retrieve → Critic (Sufficiency) → Synthesize → (Optional) Act**
* Support 3 core use cases:

  1. **ServiceNow**: question + incident context → retrieve KB context → optional action (update ticket)
  2. **Confluence**: ask for guardrails/policies → retrieve and cite
  3. **SharePoint**: Q/A over docs + optional comparison of versions (contracts/procurement)
* **Production-ready scaffolding**: contracts, telemetry spans, deployable to **Azure Container Apps**
* **Risk tiering placeholders** (do not enforce complex governance logic yet)
* **No per-user access trimming** (placeholder fields only)

### Non-goals (for now)

* Full ACL-based trimming / ABAC/RBAC enforcement (keep as schema placeholders)
* Full eval harness and regression gating (create hooks only)

---

## B) Architectural principles (rules)

1. **State machine over prompts**: the engine decides which step runs next; LLM never “free-runs.”
2. **Contracts everywhere**: every boundary is a Pydantic model (inputs/outputs) with schema versions.
3. **Modes to manage latency**: not every request uses full actor-critic.
4. **Stable core, swappable edges**:

   * Stable: `AgentWorkflowEngine`, contracts, telemetry model
   * Swappable: routers (Classic vs MAF), retrievers (Foundry IQ vs Direct Search vs APIs), tool adapters
5. **One trace per request**: propagate `correlation_id` + W3C trace context.
6. **Tool safety**: tool payload must be validated + (later) redacted before execution.

---

## C) Loop Modes (latency control)

Define `LoopMode`:

* `FAST_RAG`: Retrieve → Synthesize
* `PLAN_RAG`: Plan → Retrieve → Synthesize
* `FULL_ACTOR_CRITIC`: Plan → Retrieve → Critic → loop → Synthesize
* `ACTION_GATED`: FULL + human approval required to Act

Also define a `LoopBudget`:

* `max_iterations` (default 2)
* `max_latency_ms` (default 8000)
* `max_prompt_tokens` / `max_output_tokens`

---

## D) Required data contracts (Pydantic)

### D1) Core request + context

* `AgentRequest { request_id, thread_id, user_query, metadata, risk_tier }`
* `AgentContext { trace_context, plan, retrieval, critic, draft, final, history }`

### D2) Planning

* `QueryPlan { intents:[], subquestions:[], query_specs:[] }`
* `QuerySpec { query_text, source_preference, filters, facets, top_k, rerank, mode }`

### D3) Retrieval

* `RetrievedChunk { content_id, title, url, snippet, score, source_system, metadata }`
* `RetrievalResult { chunks:[], metrics:{ latency_ms, hit_count, source, applied_filters } }`

### D4) Critic / sufficiency

* `SufficiencyResult { sufficient: bool, confidence: float, missing_aspects:[], next_query_specs:[] }`

### D5) Tooling

* `ToolCallRequest { tool_name, schema_version, payload, idempotency_key, approval_required }`
* `ToolCallResult { status, outputs, error, retry_after_ms }`

### D6) Governance placeholders

* `GovernanceRequest { pii_mode, content_safety_mode, policy_set_id }`
* `GovernanceResult { safe: bool, pii_redacted: bool, blocks:[], severity }`

### D7) Final response

Extend `AgentResponse`:

* `response_mode`, `processing_time_ms`, `prompt_versions`, `retrieval_metrics`, `governance_result`

---

## E) Component interfaces (fungibility)

### E1) Router

`IEnterpriseRouter.route(ctx) -> RouteDecision { agent_name, loop_mode, tools_allowed }`

Implementations:

* `ClassicRouter` (stable)
* `MAFRouter` (preview, optional)

### E2) Planner

`IPlanner.plan(request, ctx) -> QueryPlan`

### E3) Retriever

`IRetriever.retrieve(plan, request, ctx) -> RetrievalResult`

Implementations:

* `FoundryIQRetriever` (managed KB via MCP / KB tool)
* `AISearchDirectRetriever` (SearchClient; your QuerySpec controls filters/facets)
* `ConfluenceApiRetriever` (via Logic Apps)
* `SharePointGraphRetriever` (via Logic Apps)

### E4) Critic

`ICritic.check(request, retrieval, ctx) -> SufficiencyResult`

### E5) Synthesizer

`ISynthesizer.write(request, retrieval, ctx) -> AgentResponse`

### E6) Tool Executor

`IToolExecutor.execute(tool_request, ctx) -> ToolCallResult`

---

## F) Engine orchestration algorithm (canonical)

Pseudo-logic:

1. Start root span, create `correlation_id`.
2. Router decides `loop_mode` + agent selection.
3. Depending on mode:

   * FAST_RAG: retrieve → synthesize
   * PLAN_RAG: plan → retrieve → synthesize
   * FULL: plan → retrieve → critic → (loop plan/retrieve if needed) → synthesize
4. If action requested and allowed:

   * validate tool payload → (optional human approval) → execute tool → append action logs
5. Output `AgentResponse` with citations and metrics.

---

## G) Prompt packs (standard vs project)

### Standard prompts (patterns repo)

* `critic_sufficiency_v1`
* `citation_format_v1`
* `tool_payload_guard_v1`

### Project prompts (projects repo)

* answer style, domain-specific language, formatting rules

Always record `prompt_version` + hash into traces and response.

---

## H) Telemetry and audit fields (placeholders)

### Required audit fields (every request)

* `correlation_id`
* `thread_id`
* `agent_name` / `project_name`
* `risk_tier` (placeholder)
* `data_sources_used` (Confluence/SharePoint/FoundryIQ/ServiceNow)
* `tools_called` (names)
* `prompt_versions`

### Risk tiering placeholder

Add simple `risk_tier: {Tier1|Tier2|Tier3}` to config and log it; don’t enforce logic yet.

---

## I) Repo layout (two-repo model)

### Patterns repo (publishable package)

* `enterprise_agent_core/`

  * `contracts/`
  * `engine/`
  * `routers/`
  * `retrieval/`
  * `tools/`
  * `telemetry/`
  * `prompts/standard/`

### Projects repo (thin)

* `use-cases/{service-now-bot|confluence-bot|sharepoint-bot}/`

  * `agent.yaml`
  * `prompts/project/`
  * `main.py` (wires dependencies)
  * `Dockerfile`
  * `.github/workflows/deploy.yaml`

---

## J) Deployment standard (ACA)

Expose a consistent container contract:

* env vars:

  * `PROJECT_ENDPOINT` (preferred)
  * `MODEL_DEPLOYMENT`
  * `ROUTER_MODE` (classic|maf)
  * `LOOP_MODE_DEFAULT`
  * `PII_MODE`, `CONTENT_SAFETY_MODE`
  * `RISK_TIER`

ACA conventions:

* Managed identity for calling Azure resources
* Key Vault references for secrets
* Health endpoints `/healthz` and `/readyz`

---

## K) Coding Agent Prompt (copy/paste)

Use this as a prompt to an AI coding agent:

* Implement Option A architecture: `AgentWorkflowEngine` is the canonical orchestrator.
* Create Pydantic contracts listed in Section D with schema_version fields.
* Implement interfaces in Section E.
* Provide a working reference use case `confluence-bot` using `AISearchDirectRetriever` (mocked) and `ClassicRouter`.
* Add telemetry spans for `plan/retrieve/critic/synthesize/tool_call` with correlation_id + thread_id attributes.
* Implement a minimal FastAPI app exposing `/chat` that accepts AgentRequest and returns AgentResponse.
* Ensure code runs locally with `uvicorn`.
* Add Dockerfile and GitHub Actions skeleton for ACA deploy.
* Do not implement per-user access trimming; include placeholders only.

Definition of Done:

* Unit tests for contracts validation and mode switching.
* A sample `agent.yaml` for each use case.
* Responses include citations (even if mocked), processing_time_ms, and audit fields.
