# Operations

Notes for running the stack for months, not days.

## Pin everything, bump on purpose

- Every image by tag **and** digest in production
  (`ghcr.io/open-webui/open-webui:v0.12.0@sha256:...`). The blueprint shows
  tags only so it stays readable. Renovate can bump tag and digest together
  (`pinDigests`); this repo's `renovate.json` leaves OpenWebUI to manual
  bumps because every minor runs DB migrations.
- Watch for upstream channel changes. A release channel that stops (e.g. a
  `-stable` suffix series ending while plain semver continues) makes
  Renovate look green while you fall behind: it only compares tags with the
  same suffix. Check the upstream tag list by hand now and then.
- Security fixes beat the schedule. The gateway is internet-facing with
  keys to every provider; subscribe to its advisories.

## Upgrade runbook (OpenWebUI, gateway)

Both run DB migrations on start and have no down-migration. The way back
from a bad upgrade is a restore, not a tag rollback.

1. **Read the changelog** between your version and the target. Note
   migrations, removed env vars, changed defaults, API changes your custom
   scripts depend on (badge, tool servers).
2. **Back up the database**: `pg_dump -Fc` of the app DB, kept off-host.
   For the gateway, keep `LITELLM_SALT_KEY` with it.
3. **Snapshot Qdrant** (for OpenWebUI): `POST /collections/<name>/snapshots`
   per collection, or a full snapshot. Snapshots land in `/qdrant/snapshots`,
   which needs its own volume (the compose files have one), or the snapshot
   is gone after the next container recreate.
4. **Canary first**: bump a non-production instance of the fleet (a test
   bench or a workshop instance on the same base) and run the checks below.
5. **Roll production**, then run the same checks there.
6. **Record** version, date, check results and anything you patched.

Checks after every bump (on the real instance, not only "container healthy"):

- SSO login as a normal user and as an admin; role and groups correct
- a chat completion on a sovereign tile and on a commercial one
- every tool server once (directory, catalog, knowledge sources)
- file upload with RAG answer, web search answer, image generation
- carbon badge shows a number; cost dashboard loads
- gateway: `/health/readiness`, all hooks present in the active callbacks

## Custom images: fail the build, not production

Patches to upstream (a `sed` on a Python file, an injected script) go into
your Dockerfile with a check that fails the build when the patch no longer
applies: `grep` for the patched line, `python -c "import ..."` for modules,
`test -f` for injected assets. Each patch carries a comment saying which
upstream bug it works around and when it can be removed.

## Database majors

A Postgres major bump is a migration, not a tag change:

- verify the application supports the target major (OpenWebUI publishes no
  matrix: restore a dump into the new major and drive the real image against
  it before switching),
- use `pg_upgrade` or an image that runs it in place (`pgautoupgrade`),
- keep the same libc family (Debian to Alpine changes collation order under
  existing indexes),
- note the data-directory layout change of the official Postgres 18 images
  (`/var/lib/postgresql/18/docker`).

## Container hygiene

- `init: true` on OpenWebUI (and anything that spawns subprocesses per
  request): an init process reaps zombie children.
- Healthchecks that test readiness, not an open port (Qdrant `/readyz`,
  LiteLLM `/health/readiness`).
- Redis for OpenWebUI with AOF on; for the gateway, router state only, with
  `maxmemory` and LRU eviction.

## Runtime config lives in databases

Gateway models, aliases, credentials, fallbacks and keys; OWUI tiles,
prompts, permissions, tool connections and filters: all in Postgres, edited
through admin UIs and APIs. Consequences:

- Back up both databases like application data, daily.
- Export what you want reviewable (gateway catalog and router settings, OWUI
  model and group config) to git on a schedule, as a record, not as the
  source of truth.
- OWUI caches PersistentConfig in Redis. After a direct DB write, delete the
  cached key and restart, or the old value keeps winning.

## Budgets

The reference deployment tracks spend per person, key and team and sets no
budgets by default: blocking a researcher mid-task costs more than the
tokens. Hard caps go on individual keys where a runaway is plausible (a
public instance, an unattended indexer using paid fallbacks).
