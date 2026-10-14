# Multi-tenancy: a fleet of OpenWebUI instances

How to run more than one OpenWebUI next to each other without interference.
Useful for: workshops where each cohort gets its own instance, exhibitions
or artworks with their own chat surface, a test bench for upgrades,
departments that want isolation.

## The pattern

One shared base compose file, one tiny compose file per instance:

```
webui/docker-compose.yml                       # base: images, env, services
webui/instances/<name>/docker-compose.yml      # name: ${STACK} + include: base
webui/instances/<name>/.env                    # everything instance-specific
```

Each instance gets:

- its own project name (`STACK`), so containers, volumes and the Traefik
  router name don't collide
- its own hostname
- its own volumes and Postgres (separate chat history, separate vectors)
- **its own virtual key on the shared `gateway/`**, scoped to the models
  that audience may use, so spend is attributable per instance
- the shared `cost-tracker/` sees all instances in one ledger

Bumping OWUI or fixing an env var in the base updates every instance. That
is the reason for `include:` over copying the folder: copies drift.

## Bring up a new instance

```bash
cp -r webui/instances/example-workshop webui/instances/workshop-march
cd webui/instances/workshop-march
cp .env.example .env
$EDITOR .env      # STACK, WEBUI_DOMAIN, fresh secrets, its own virtual key
docker compose up -d
```

With a GitOps tool (Portainer, Argo, Flux, plain cron + git pull): one
directory or branch per instance, all pointing at the same base. Keep the
instance's secrets in the tool's stack env, not in git.

## Decisions to make per instance

- **Local accounts or OIDC?** Workshops with external participants: local
  accounts, admin creates them. Internal instances: same OIDC wiring as the
  main instance, possibly a different allowed group.
- **Model scope.** Scope the instance's virtual key to the aliases it needs.
  A workshop that only needs one sovereign chat model should not hold a key
  that unlocks commercial models.
- **Budget?** The reference deployment tracks instead of capping. If an
  instance is open to the public, a `max_budget` on its key is the simple
  hard stop.
- **Embeddings.** An instance without a gateway embedding alias can fall
  back to OWUI's local SentenceTransformers. Costs CPU and image size, saves
  nothing worth it if the gateway is there.
- **Lifetime.** Tear down with `docker compose down -v` (removes chats and
  vectors) and revoke its virtual key.

## Promote upgrades through the fleet

Use one non-production instance as the canary: bump the base there first
(see [`../docs/operations.md`](../docs/operations.md)), check sign-in, chat,
tools, uploads, then roll the rest.

## What doesn't generalise

All instances share one Docker host and one gateway. If tenants must be
isolated against a compromised neighbour (different institutions on one
host), use separate hosts.
