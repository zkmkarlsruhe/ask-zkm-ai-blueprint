# Postgres vs. SQLite for OpenWebUI

Since 0.2.0, `webui/docker-compose.yml` runs OpenWebUI on **Postgres** by
default. SQLite stays an option for evaluation and very small installs.

## Why Postgres is the default

- **Per-user spend dashboards** in `cost-tracker/` read OWUI's `user` table
  from another container. SQLite can't be read from outside the OWUI
  container. Postgres can (over the `ai-bus` network).
- **Concurrent writes** at scale (>50 active users, long chats, many file
  uploads) hit SQLite's writer lock. Symptoms: chat saves stalling,
  "database is locked" in OWUI logs.
- **Backups and upgrades**: `pg_dump` before every OWUI bump gives you a
  restore point for the DB migrations each minor version runs.

## Running on SQLite instead

In `webui/docker-compose.yml`:

1. Remove the `DATABASE_URL` line from `open-webui.environment`.
2. Remove the `postgres` service, its `depends_on` entry and the
   `postgres_data` volume.

OWUI then keeps `webui.db` in the `openwebui_data` volume. `cost-tracker/`
can still serve the carbon page and API (they read only the gateway's DB);
the per-user dashboard cannot resolve names.

## Moving an existing SQLite install to Postgres

OWUI ships no migration tool. Two options:

- **Fresh start (easiest)**: bring up Postgres, OWUI creates its schema on
  first boot, sign in as admin, re-onboard users via OIDC. Old chats stay in
  the SQLite volume.
- **Copy the data**: a generic tool such as `pgloader` can move the tables;
  run it against a stopped OWUI of the *same* version, then start that
  version on Postgres before bumping anything. Test on a copy first.

## Postgres versions

- Pin the major version. A major bump (17 to 18) needs `pg_upgrade` (or an
  image like `pgautoupgrade` that runs it in place on first start), not just
  a tag change.
- The official Postgres 18 images keep data under
  `/var/lib/postgresql/18/docker` and expect the volume at
  `/var/lib/postgresql`. A volume that older images used at
  `/var/lib/postgresql/data` does not start under 18 unchanged.
- Stay on the same libc family when upgrading in place (Debian to Alpine
  changes collation order under existing indexes).
- OWUI publishes no Postgres support matrix. Before a major bump, restore a
  dump into the new version and drive the real image against it (sign in,
  list and search chats, run a completion) before you switch production.

## Notes

- Keep the volume on a fast disk.
- Don't share the instance with other applications: one DB per service.
