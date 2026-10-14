# Wiring

How the components find each other. Three things to get right: networks, env
vars, secrets.

## Networks

Create the two shared docker networks once, before anything else:

```bash
docker network create proxy     # everything that needs to be reachable from outside
docker network create ai-bus    # cost-tracker reads the gateway's and webui's DBs across this
```

Each stack's `docker-compose.yml` declares these as `external: true`. Internal
networks (`backend`, `webui_backend`) are created automatically per stack.

## Bring-up order

| # | Stack | Why this order |
|---|---|---|
| 1 | `gateway/` | webui needs a base URL to point at, and a virtual key for the instance minted with the master key |
| 2 | `webui/` | needs gateway up; first user becomes admin |
| 3 | `cost-tracker/` (optional) | needs both postgres instances reachable on `ai-bus` |
| 4 | `mcps/*` (optional) | each one independent; connect to webui's network after bring-up |

## The env-var handshakes

### gateway → webui

In `gateway/`:
- `GATEWAY_DOMAIN=api.your-house.org`
- mint **one** virtual key for this OpenWebUI instance (`/key/generate`
  with the master key), scoped to the aliases the instance may use

In `webui/.env`:
- `LITELLM_API_BASE=https://api.your-house.org/v1`
- `LITELLM_VIRTUAL_KEY=sk-the-virtual-key`

OpenWebUI now sees the aliases the key may call. Per-user spend is attributed
because `webui/` sets `ENABLE_FORWARD_USER_INFO_HEADERS=true`: OWUI sends
`X-OpenWebUI-User-Id` (plus email, name, role, chat id) with every call, and
the gateway's `user_header_mappings` records the id as the spend row's
`user`. One key per instance, not one per person.

### gateway → cost-tracker

In `cost-tracker/.env`:
- `LITELLM_DB_URL=postgresql://litellm:<gateway POSTGRES_PASSWORD>@litellm-db:5432/litellm`

`litellm-db` is the gateway postgres's alias on `ai-bus`. Every stack calls
its DB service `postgres`, so the shared network uses unique aliases.

### webui → cost-tracker

The dashboard shows names, so cost-tracker also reads OWUI's `user` table.
`webui/` runs on Postgres by default and puts its DB on `ai-bus` as
`<STACK>-db`:

- `OPENWEBUI_DB_URL=postgresql://openwebui:<OWUI_POSTGRES_PASSWORD>@webui-db:5432/openwebui`

On SQLite, skip this; the carbon page still works.

### MCPs → webui

In each MCP's `docker-compose.yml`, add a network OpenWebUI is on (webui's
backend network, or a shared `proxy`/tools network if several instances use
the same MCP):

```yaml
networks:
  webui_backend:
    external: true
    name: webui_backend
```

(The name is `<webui-stack-name>_backend` — find it with `docker network ls`.)
Then in OpenWebUI: **Admin Panel → Settings → Integrations → Tool Servers →
"+"** with URL `http://<service-name>:8000/mcp`, and bind it to the models
that should use it.

### webui → MCPs (returning data)

No env wiring needed — MCPs respond to the HTTP call OWUI makes. With
`ENABLE_FORWARD_USER_INFO_HEADERS=true` the call carries the user's id and
email, so a tool can answer for the asking person.

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

# Carbon page renders (public host)? Per-user API refused there?
curl https://$CARBON_DOMAIN/carbon
curl -o /dev/null -w '%{http_code}\n' https://$CARBON_DOMAIN/api/users/costs   # 404
```

If these return 200 (404 for the last one) and the gateway lists at least one model, you have a
working stack. Onboard the first user to OWUI now (they become admin), then
disable signup in `webui/.env` and finish the OIDC wiring per
[`auth.md`](auth.md).
