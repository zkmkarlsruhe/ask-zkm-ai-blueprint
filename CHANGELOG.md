# Changelog

All notable changes to this blueprint will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are dated snapshots, not semver — this is a reference
implementation, not a library you depend on.

## [Unreleased]

## [0.2.0] — 2026-10-14

Snapshot of the reference deployment as it runs today.

### Changed

- **Versions:** OpenWebUI v0.12.0, LiteLLM v1.104.0 (tag-pinned; digest
  pinning documented), Qdrant v1.19.2, Redis 8.10.2-alpine, Postgres 18 for
  OpenWebUI, FastMCP >= 4.0.10 (verified on 4.1.0), Python 3.14-slim for
  cost-tracker and hello-world.
- **Attribution model corrected:** one virtual key per instance, not per
  user. OpenWebUI forwards the user via `ENABLE_FORWARD_USER_INFO_HEADERS`;
  the gateway maps `X-OpenWebUI-User-Id` with `user_header_mappings` and tags
  email, role and chat id via `extra_spend_tag_headers`.
- `gateway/`: router settings (`usage-based-routing-v2`, `num_retries`,
  fallback example), `drop_params`, batched spend writes, DB-only admin
  login, readiness healthcheck, `USE_PRISMA_MIGRATE`. Dropped the
  `postgres` success callback and the Redis response cache (not used in
  production); Redis now holds router state only.
- `webui/`: Postgres is the default app DB (SQLite optional), `init: true`,
  Qdrant snapshots volume and readiness probe, embeddings through the
  gateway, OIDC role and group management via env, Redis lock and keepalive
  settings, stream buffer for inline images.
- `webui/customizations/`: carbon badge reads the user id from the session
  JWT, calls `/api/carbon/{user_id}`, links with `?amount=`; Dockerfile has a
  build smoke test.
- `cost-tracker/`: spend in EUR split into invoiced and shadow
  (`SHADOW_API_BASE_RE`); per-user dashboard and API host-gated to
  `DASHBOARD_HOST` (fail closed), public carbon host routes carbon paths
  only; page copy moved to `content/carbon_info.yaml`; build-time self-check.
- `mcps/opac/`: catalog URL, profile, name and focus via env with
  placeholder defaults; `/health` route.
- `proxies/document-preprocessor/`: now a docling-serve-compatible shim
  (`/v1/convert/file`) in front of a convert upstream.
- Shared `ai-bus` network uses unique DB aliases (`litellm-db`,
  `<STACK>-db`); the LiteLLM container itself is off `ai-bus`.
- CI: ruff findings under current ruff defaults fixed; new compose
  variables added to the validation step; `gateway/hooks` linted.

### Added

- `gateway/Dockerfile.example` + `gateway/hooks/example_hook.py`: hooks
  baked into a custom image with import and behaviour smoke tests.
- `webui/instances/`: multi-instance fleet, one `include` of the base per
  instance.
- Docs: `aliases.md` (alias-first, fan-out, fallback rules, embedding and
  rerank never fall back), `tiers.md` (user / expert / guru via IdP groups,
  permissions, per-model grants), `knowledge-mcp.md` (crawler -> store ->
  ingestor -> Qdrant, one MCP endpoint per source), `web-search.md`
  (SearXNG + Firecrawl v2), `document-extraction.md`, `operations.md`
  (pinning, upgrade runbook: pg_dump -> Qdrant snapshot -> canary).
- `auth.md`: full identity flow, auto-onboarding, offboarding caveat
  (session JWT lifetime, data retention).

### Removed

- Claims that no longer match production: knowledge sync into OpenWebUI
  Knowledge collections, model proxies in front of the gateway, a Firecrawl
  v1-to-v2 translation proxy (obsolete since OpenWebUI 0.9.2).
- Event references in the README and changelog.

## [0.1.0] — 2026-05-05

Initial public release.

### Added

- `gateway/` — LiteLLM proxy with commented stubs for academic, local, and
  commercial providers
- `webui/` — OpenWebUI + Qdrant + Redis stack with interactive `gen-env.sh`
  and opt-in customizations (carbon badge, sidebar links)
- `mcps/hello-world/` — minimal FastMCP starter template
- `mcps/opac/` — full working library-catalog MCP (BSZ aDISWeb)
- `proxies/oauth-translator/` — OAuth2 client-credentials → bearer skeleton
- `proxies/local-bridge/` — aliasing + ceilings in front of self-hosted LLMs
- `proxies/document-preprocessor/` — office files → clean text for RAG
- `cost-tracker/` — per-user spend dashboard + public carbon footprint page
- `docs/` — architecture, wiring, auth (OIDC), adapting checklist
- `examples/` — Traefik snippet, Postgres-vs-SQLite, multi-tenancy patterns
