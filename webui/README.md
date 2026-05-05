# webui/ — OpenWebUI + Qdrant + Redis

The chat surface your users see. Three containers, one network, no provider
keys (those live in `gateway/`).

## What's here

- `docker-compose.yml` — OWUI + Qdrant (vector DB for RAG) + Redis (sessions).
- `gen-env.sh` — interactive `.env` generator. Run as `./gen-env.sh > .env`.
- `.env.example` — annotated reference for what each variable does.
- `customizations/` — opt-in: in-chat CO₂ badge, custom sidebar links, and a
  Dockerfile that bakes them into the image.

## Bring up

```bash
./gen-env.sh > .env                          # or copy .env.example
docker network create proxy 2>/dev/null
docker compose up -d
```

First user to sign in becomes admin. After that, set `ENABLE_SIGNUP=false` in
`.env` (already the default), restart, and onboard everyone else through OIDC.

## Wiring it to gateway/

OWUI talks to the gateway over HTTP, just like any other OpenAI-compatible
client. Two env vars do the work:

```
LITELLM_API_BASE=https://api.your-house.org/v1
LITELLM_VIRTUAL_KEY=sk-...     # mint in LiteLLM admin UI, not the master key
```

After bring-up, in OWUI's admin settings the model list will populate from
whatever you registered in `gateway/config.yaml`.

## Wiring it to your IdP

OIDC env vars are commented in `docker-compose.yml`. The full pattern (group
claim → role mapping, disabling local login, the bootstrap-admin trick) lives
in [`../docs/auth.md`](../docs/auth.md).

## Customizations (optional)

Three things you almost certainly want eventually:

1. **In-chat CO₂ badge** — `customizations/carbon-badge.js`. Polls
   `cost-tracker/`'s public `/carbon/{user_id}` endpoint and shows a small
   badge in the corner. The "fourth guarantee" made literal.
2. **House links in the sidebar** — `customizations/sidebar-links.js`. Adds
   a Privacy Notice, Documentation, and Report-a-Problem link to the bottom
   of the left sidebar.
3. **Branding** — favicon, splash logo, custom CSS. Drop into `brand/` and
   uncomment the relevant `COPY` line in `Dockerfile.example`.

To use them, build the customised image and switch `image:` for `build:` in
`docker-compose.yml`:

```bash
docker build -f customizations/Dockerfile.example -t my-museum-owui:local .
```

```yaml
# docker-compose.yml
services:
  open-webui:
    # image: ghcr.io/open-webui/open-webui:0.7.2
    build:
      context: .
      dockerfile: customizations/Dockerfile.example
```

The customization scripts are starting points — DOM selectors and storage keys
inside OWUI shift between versions. Test, then commit your version-pinned
adaptation in your own fork.

## Storage

OWUI defaults to **SQLite** in `/app/backend/data` (the `openwebui_data`
volume). That's fine for evaluation and small houses. For >50 active users or
HA, switch to Postgres — see [`../examples/postgres-vs-sqlite.md`](../examples/postgres-vs-sqlite.md).

## Notes

- **Pin OWUI's version.** The `image:` tag here is exact, not `latest`. OWUI
  ships frequently and breaking changes are normal. Bump intentionally.
- **`WEBUI_AUTH=true` is non-negotiable** for any deployment that isn't your
  laptop. Setting it to false disables all authentication.
- **Qdrant in single-tenant mode** is the default here. For workshop /
  multi-tenant setups (one OWUI per cohort, shared Qdrant), set
  `ENABLE_QDRANT_MULTITENANCY_MODE=true` and read the Qdrant docs.
