# Architecture

```
          Identity provider (any OIDC IdP)
          groups claim: ai-user / ai-expert / ai-guru / ai-admin
                    |
                    | OIDC login, groups -> role + OWUI groups
                    v
   +------------------------------------------------+
   | webui/  OpenWebUI (one or many instances)      |
   |  tiles, prompts, permissions, filters (Postgres)|
   |  uploads -> volume or S3, RAG vectors -> Qdrant |
   |  carbon badge (JS)                              |
   +------------------------------------------------+
      | model calls                | tool calls       | web + documents
      | + X-OpenWebUI-User-*       | + X-OpenWebUI-*  |
      v                            v                  v
   +----------------------+  +--------------------+  +--------------------------+
   | gateway/  LiteLLM    |  | MCP tool servers   |  | SearXNG (search)         |
   | aliases house/*      |  |  directory (+ /me) |  | Firecrawl v2 (fetch)     |
   | credentials, routing |  |  catalog (opac)    |  | docling-compatible       |
   | fallbacks, spend     |  |  knowledge-base:   |  |  extraction --> provider |
   | hooks, Postgres,Redis|  |   one MCP / source |  +--------------------------+
   +----------------------+  +--------------------+
      |         |                 |  crawler -> store -> ingestor -> Qdrant
      |         |                 +--> embeddings via gateway
      |         v
      |   +--------------------------+     +-------------------------------+
      |   | cost-tracker/            |     | upstream providers            |
      |   |  dashboard (protected)   |     |  academic / EU first          |
      |   |  carbon page + API       |     |  commercial: visible opt-in   |
      |   |  (public)                |     |  embed + rerank: no fallback  |
      |   +--------------------------+     |  self-hosted                  |
      |     reads spend logs + users       +-------------------------------+
      +------------------------------------------------^
```

## Why this shape

**One gateway for everything that costs tokens** is the load-bearing
decision. Chat, task generation (titles, tags, search queries), embeddings,
rerank, image generation and editing, speech-to-text and text-to-speech all
go through LiteLLM. With one gateway:
- every token is logged against a person (OpenWebUI forwards the user id in
  a header; one virtual key per instance, not per person),
- providers, credentials, aliases and fallbacks live in one place; a model
  swap is one API call, not a sweep through every client,
- carbon and cost calculations have one source of truth,
- the auditor's question "what data left this building, to whom?" has one
  answer per alias.

**What does not go through the gateway, on purpose:**

| Piece | Why not |
|---|---|
| Tool servers (MCP / OpenAPI) | Called by OpenWebUI's tool loop, which also carries the identity headers. LiteLLM's MCP gateway is not used. |
| Web search (SearXNG) and page fetch (Firecrawl v2) | Search engine and scraper, not models. |
| Document extraction (docling-compatible) | Not an OpenAI-shaped API; its key lives in the extraction shim. |
| Login (OIDC IdP) | Identity, not inference. |
| OpenWebUI runtime config | Tiles, prompts, permissions, filters are product logic in OWUI's DB. |

List these explicitly in your data-flow documentation. They are the paths
that bypass the gateway's ledger.

**Separate databases.** LiteLLM has its own Postgres (models, keys,
credentials, spend). Each OpenWebUI instance has its own (chats, users,
permissions). The cost-tracker reads both — that join is the cost system.

**Qdrant + Redis are private to each webui instance.**

**Knowledge comes from the house's own sources through MCP**, not from
files uploaded into OWUI knowledge collections: one central service crawls
and indexes the sources and exposes one MCP endpoint per source. See
[`knowledge-mcp.md`](knowledge-mcp.md).

## Networks

| Network | Purpose | Members |
|---|---|---|
| `proxy` | reverse-proxy ingress, tool servers | webui instances, gateway, cost-tracker, MCPs |
| `ai-bus` | inter-stack DB reads | gateway postgres (`litellm-db`), webui postgres (`<STACK>-db`), cost-tracker |
| `<stack>_backend` | each stack's internals | private |

Create the shared ones once: `docker network create proxy ai-bus`.

## Where state lives

| State | Where | Back up |
|---|---|---|
| Models, aliases, credentials, fallbacks, keys, spend | gateway Postgres | yes, with `LITELLM_SALT_KEY` |
| Users, chats, tiles, prompts, permissions, tool bindings | webui Postgres | yes |
| Uploads | `openwebui_data` volume or S3 | yes |
| RAG vectors | Qdrant (+ snapshots volume) | snapshot before upgrades; rebuildable from uploads at a cost |
| Sessions, config cache | Redis | no |

Much of the behaviour is runtime config in two databases, not in git. That
is a deliberate trade: the gateway and OWUI apply changes without a restart.
The price is that git does not describe the running system; the DBs do.

## What's NOT shown above

- **Reverse proxy / TLS.** Required, not bundled. See
  [`../examples/traefik-snippet.yml`](../examples/traefik-snippet.yml).
- **Monitoring.** LiteLLM exposes `/metrics`; containers log to stdout.
- **Operations** (upgrades, snapshots, canaries): [`operations.md`](operations.md).

## What the reference deployment adds on top

- a custom OWUI image (carbon badge, house links, branding, small upstream
  patches applied with build-time checks),
- custom gateway image with provider-compatibility hooks,
- house-specific MCPs (directory, catalog, knowledge base, archive),
- a small fleet of additional OWUI instances (workshops, test bench,
  artworks) on the same gateway.

The blueprint here is the part that generalises.
