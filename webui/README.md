# webui/ — OpenWebUI + Postgres + Qdrant + Redis

The chat surface your users see. Four containers, no provider keys (those
live in `gateway/`).

## What's here

- `docker-compose.yml` — OWUI v0.12.0 + Postgres (app DB) + Qdrant (vectors)
  + Redis (websockets, sessions, config cache). Also the base for a fleet.
- `instances/` — one directory per additional instance, each a three-line
  compose file that includes the base.
- `gen-env.sh` — interactive `.env` generator. Run as `./gen-env.sh > .env`.
- `.env.example` — annotated reference for what each variable does.
- `customizations/` — opt-in: in-chat CO₂ badge, custom sidebar links, and a
  Dockerfile that bakes them into the image with a build smoke test.

## Bring up

```bash
./gen-env.sh > .env                          # or copy .env.example
docker network create proxy  2>/dev/null
docker network create ai-bus 2>/dev/null
docker compose up -d
```

First user to sign in becomes admin. After that, set `ENABLE_SIGNUP=false` in
`.env` (already the default), restart, and onboard everyone else through OIDC.

## Wiring it to gateway/

```
LITELLM_API_BASE=https://llm.zkm.tech/v1
LITELLM_VIRTUAL_KEY=sk-...     # one key per instance, not the master key
```

`ENABLE_FORWARD_USER_INFO_HEADERS=true` is set in the compose file. OpenWebUI
then sends `X-OpenWebUI-User-Id/-Email/-Name/-Role` and
`X-OpenWebUI-Chat-Id` with every model call, and the gateway attributes spend
per person from that header. Tool servers receive the same headers, which is
how a directory MCP can answer "who am I".

Embeddings run through the gateway as well (`RAG_EMBEDDING_MODEL`, an alias
without fallback). Task model (titles, tags, search queries) is set in the
admin UI; point it at an alias on your most private provider, because it sees
real chat content.

## Wiring it to your IdP

OIDC, role mapping and group sync are env-driven and empty by default. Login
pattern: [`../docs/auth.md`](../docs/auth.md). Groups, tiers and per-model
access: [`../docs/tiers.md`](../docs/tiers.md).

## Optional: web search and document extraction

Both are off by default and commented in `docker-compose.yml`:

- SearXNG (finds URLs) + Firecrawl v2 (fetches pages as markdown):
  [`../docs/web-search.md`](../docs/web-search.md)
- docling-compatible extraction service for uploads:
  [`../docs/document-extraction.md`](../docs/document-extraction.md)

## A fleet of instances

Production rarely has one instance. Workshops, exhibitions, test benches and
individual projects each want their own OWUI with their own users and model
scope, sharing one gateway. Pattern:

```
webui/docker-compose.yml                    # the base, bumped once
webui/instances/example-workshop/
    docker-compose.yml                      # name: ${STACK} + include: base
    .env                                    # STACK, domain, key, secrets
```

```bash
cd instances/example-workshop
cp .env.example .env && $EDITOR .env
docker compose up -d
```

Each instance gets its own project name (`STACK`), Traefik router, volumes,
database and virtual key. Bumping OWUI in the base updates the fleet. With a
GitOps tool, one branch or one directory per instance works; keep the base
shared. Test a bump on a non-production instance first (see
[`../docs/operations.md`](../docs/operations.md)).

## Customizations (optional)

1. **In-chat CO₂ badge** — `customizations/carbon-badge.js`. Polls
   `cost-tracker/`'s public `/api/carbon/{user_id}` endpoint and shows a small
   badge linking to the public carbon page.
2. **House links in the sidebar** — `customizations/sidebar-links.js`.
3. **Branding** — favicon, splash logo, custom CSS. Drop into `brand/` and
   uncomment the relevant `COPY` line in `Dockerfile.example`.

```bash
docker build -f customizations/Dockerfile.example -t my-museum-owui:local .
```

```yaml
# docker-compose.yml
services:
  open-webui:
    # image: ghcr.io/open-webui/open-webui:v0.12.0
    build:
      context: .
      dockerfile: customizations/Dockerfile.example
```

DOM selectors and storage keys inside OWUI shift between versions. The
Dockerfile ends with a smoke test that fails the build if the injection did
not land; re-test the badge after every OWUI bump.

## Storage

Postgres is the default app DB. SQLite works for evaluation; the cost
dashboard's name join and most operational tooling assume Postgres. See
[`../examples/postgres-vs-sqlite.md`](../examples/postgres-vs-sqlite.md).
Uploads go to the `openwebui_data` volume; OWUI can also store them in S3
(`STORAGE_PROVIDER=s3`).

## Notes

- **Pin OWUI's version.** Tag here, tag plus digest in production. Bump
  intentionally; every minor version runs DB migrations.
- **Runtime config lives in the DB.** Model tiles, system prompts, group
  permissions, tool bindings, filters, RAG settings: the admin UI writes them
  to Postgres, cached in Redis. Env vars marked PersistentConfig only seed a
  fresh DB. After a direct DB change, clear the Redis config key and restart,
  or the cached value wins.
- **`WEBUI_AUTH=true` is non-negotiable** for any deployment that isn't your
  laptop.
- **Qdrant multitenancy mode** is on: all users' collections share a few
  physical collections partitioned by tenant, which keeps Qdrant's memory flat
  as users grow.
