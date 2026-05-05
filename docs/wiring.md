# Wiring

How the components find each other. Three things to get right: networks, env
vars, secrets.

## Networks

Create the two shared docker networks once, before anything else:

```bash
docker network create proxy     # everything that needs to be reachable from outside
docker network create ai-bus    # cost-tracker reads gateway's DB across this
```

Each stack's `docker-compose.yml` declares these as `external: true`. Internal
networks (`backend`, `webui_backend`) are created automatically per stack.

## Bring-up order

| # | Stack | Why this order |
|---|---|---|
| 1 | `gateway/` | webui needs an `OPENAI_API_BASE_URL` to point at, and a virtual key minted from LiteLLM admin |
| 2 | `webui/` | needs gateway up; first user becomes admin |
| 3 | `cost-tracker/` (optional) | needs gateway's postgres reachable on `ai-bus` |
| 4 | `mcps/*` (optional) | each one independent; connect to webui's network after bring-up |

## The env-var handshakes

### gateway → webui

In `gateway/`:
- `GATEWAY_DOMAIN=api.your-house.org`
- mint a virtual key in LiteLLM admin UI (`/key/generate` with the master key)

In `webui/.env`:
- `LITELLM_API_BASE=https://api.your-house.org/v1`
- `LITELLM_VIRTUAL_KEY=sk-the-virtual-key`

OpenWebUI now sees whatever models you registered in `gateway/config.yaml`.
Per-user spend is automatically attributed because OWUI sends the user's id in
the `user` field of every chat completion request, and LiteLLM logs it.

### gateway → cost-tracker

In `cost-tracker/.env`:
- `LITELLM_DB_URL=postgresql://litellm:<gateway POSTGRES_PASSWORD>@postgres:5432/litellm`

The hostname `postgres` resolves on the `ai-bus` network because
`gateway/docker-compose.yml` puts its postgres service on it.

### webui → cost-tracker (optional, for per-user dashboards)

If you want the cost dashboard to show user *names* and not just opaque ids,
cost-tracker also needs to read OWUI's user table. OWUI defaults to SQLite,
which can't be read from another container. You have two options:

1. **Skip the join.** Cost-tracker shows user ids only. Carbon page still works.
2. **Switch OWUI to Postgres.** See
   [`../examples/postgres-vs-sqlite.md`](../examples/postgres-vs-sqlite.md).
   Then point `OPENWEBUI_DB_URL` at it.

### MCPs → webui

In each MCP's `docker-compose.yml`, add webui's backend network:

```yaml
networks:
  webui_backend:
    external: true
    name: webui_backend
```

(The name is `<webui-stack-name>_backend` — find it with `docker network ls`.)
Then in OpenWebUI: **Settings → Tools → "+"** with URL
`http://<service-name>:8000/mcp`.

### webui → MCPs (returning data)

No env wiring needed — MCPs respond to the HTTP call OWUI makes. The MCP
session lives only as long as the chat turn does.

## Ports

By default, only the reverse proxy exposes ports outside the docker host.
Internal services talk by service name on docker networks. The example
`docker-compose.yml` files in `mcps/hello-world/` and `mcps/opac/` map a port
to the host **only for local testing** — remove those `ports:` blocks before
production.

## Secrets

Every secret in this stack is generated locally; nothing is shared with us or
anyone else. Generate with:

```bash
openssl rand -hex 32      # for *_SECRET_KEY, *_MASTER_KEY (32-byte)
openssl rand -hex 24      # for *_PASSWORD, *_API_KEY (24-byte)
```

Use the `gen-env.sh` in `webui/` as a pattern for your own bring-up scripts.

## Sanity check after bring-up

```bash
# Gateway alive?
curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" https://$GATEWAY_DOMAIN/v1/models

# Webui alive?
curl https://$WEBUI_DOMAIN/health

# Cost-tracker alive?
curl https://$COST_DOMAIN/health

# Carbon page renders?
curl https://$COST_DOMAIN/carbon
```

If all four return 200 and the gateway lists at least one model, you have a
working stack. Onboard the first user to OWUI now (they become admin), then
disable signup in `webui/.env` and finish the OIDC wiring per
[`auth.md`](auth.md).
