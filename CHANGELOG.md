# Changelog

All notable changes to this blueprint will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are dated snapshots, not semver — this is a reference
implementation, not a library you depend on.

## [Unreleased]

## [0.1.0] — 2026-05-05

Initial public release, accompanying the MAI-Tagung 2026 talk
*"Prompting ohne schlechtes Gewissen"* at Frankfurt, 28 May.

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
