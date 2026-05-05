# Multi-tenancy: workshop and instructor tenants

How to run more than one OpenWebUI on the same host without interference.
Useful for: workshops where each cohort gets its own instance, instructors
who want a separate sandbox, departments that want isolation.

## The pattern

Each tenant is a full copy of the `webui/` stack with:

- a unique `name:` in `docker-compose.yml` (so docker doesn't collide on
  service names)
- a unique hostname (`workshop-2026-march.chat.your-house.org`)
- its own volumes (separate chat history, separate Qdrant data)
- **shared `gateway/`** — every tenant talks to the same model provider
  registry, with separate virtual keys so spend is attributable per-tenant
- **shared `cost-tracker/`** — sees all tenants in one dashboard

This is exactly what ZKM uses for workshop tenants: same gateway, same cost
tracker, isolated chat surfaces.

## Bring up a new tenant

```bash
# 1. Copy the webui/ folder to a tenant-specific name.
cp -r webui/ tenants/workshop-march/

# 2. Edit the new docker-compose.yml: change name + hostname.
cd tenants/workshop-march/
sed -i 's/^name: webui$/name: workshop-march/' docker-compose.yml

# 3. Generate fresh secrets and a unique hostname.
./gen-env.sh > .env
$EDITOR .env                 # set WEBUI_DOMAIN to a unique subdomain

# 4. Mint a virtual key in LiteLLM admin specifically for this tenant.
#    Use it for LITELLM_VIRTUAL_KEY in this tenant's .env.
#    Now spend is per-tenant in cost-tracker.

# 5. Up.
docker compose up -d
```

## Decisions to make per-tenant

- **Local-only auth or full OIDC?** Workshops with external participants who
  don't have your IdP account: enable local signup for the tenant's domain,
  set per-tenant admin manually. Internal tenants: same OIDC config as the
  main `webui/`.
- **Per-tenant model allowlist?** LiteLLM virtual keys can be scoped to a
  subset of models. If a workshop only needs cheap/local models, don't give
  it the key that unlocks the expensive ones.
- **Per-tenant budget?** Set on the virtual key in LiteLLM admin. Tenant
  hits the cap, requests start failing with a clear message. The cap is
  per-day or per-month.
- **Lifetime?** Workshop tenants exist for a fixed period. Tear them down
  cleanly: `docker compose down -v` removes the volumes (chats + Qdrant
  data) too.

## What stays shared

- `gateway/` — one LiteLLM, one model registry, one spend log
- `cost-tracker/` — one dashboard showing all tenants
- `proxy` and `ai-bus` networks
- Reverse proxy + TLS

## What doesn't generalise

If you need *strong* tenant isolation — e.g. different houses sharing one
host, where one tenant must not see another tenant's chat content even if a
DB user got compromised — this pattern is not it. Each tenant has its own DB
user, but they live in the same Docker host. For real isolation, separate
hosts.

For workshops, classrooms, "give the volunteer team their own sandbox" — this
is exactly enough.
