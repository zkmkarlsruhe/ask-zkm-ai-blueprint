# Postgres vs. SQLite for OpenWebUI

OWUI defaults to SQLite. That's fine for evaluation, demos, and houses with
under ~50 active users. For everyone else, Postgres.

## Why switch

- **Per-user spend dashboards** in `cost-tracker/` need to read OWUI's `user`
  table from another container. SQLite can't be read from outside the OWUI
  container. Postgres can.
- **Concurrent writes** at scale (>50 active users, lots of long chats) start
  hitting SQLite's writer lock. Symptoms: chat saves stalling, "database is
  locked" errors in OWUI logs.
- **Backups become trivial** with `pg_dump` instead of "stop OWUI, snapshot
  the volume".

## How to switch

### 1. Add a Postgres service to webui/docker-compose.yml

```yaml
services:
  open-webui:
    environment:
      DATABASE_URL: postgresql://${OWUI_POSTGRES_USER}:${OWUI_POSTGRES_PASSWORD}@owui-postgres:5432/${OWUI_POSTGRES_DB}
    depends_on:
      owui-postgres:
        condition: service_healthy
    networks:
      - proxy
      - backend
      - ai-bus     # so cost-tracker can reach owui-postgres

  owui-postgres:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${OWUI_POSTGRES_USER}
      POSTGRES_PASSWORD: ${OWUI_POSTGRES_PASSWORD}
      POSTGRES_DB: ${OWUI_POSTGRES_DB}
    volumes:
      - owui_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${OWUI_POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend
      - ai-bus

volumes:
  openwebui_data: {}
  owui_postgres_data: {}     # add this
```

### 2. Migrate from SQLite to Postgres

If you already have data in SQLite that you want to keep, OWUI doesn't ship a
migration tool. Two options:

- **Fresh start (easiest)**: bring up Postgres, OWUI creates its schema on
  first boot, sign in as admin, re-onboard users via OIDC. Your old chats are
  abandoned in the SQLite volume.
- **Manual migration**: `sqlite3 webui.db .dump`, hand-edit the SQL to be
  Postgres-compatible (mostly: rename `INTEGER PRIMARY KEY AUTOINCREMENT` to
  `SERIAL`, change `BLOB` to `BYTEA`, fix quote styles), `psql -f` into the
  new DB. Not for the faint of heart.

For most houses, fresh-start is the right call. People care less about old
chat history than you'd think.

### 3. Wire cost-tracker

In `cost-tracker/.env`:

```
OPENWEBUI_DB_URL=postgresql://${OWUI_POSTGRES_USER}:${OWUI_POSTGRES_PASSWORD}@owui-postgres:5432/${OWUI_POSTGRES_DB}
```

Per-user spend dashboards now show names instead of opaque ids.

## Notes

- Pinning a Postgres major version is mandatory. Bumping major versions
  (16 → 17) requires a `pg_upgrade` dance, not just changing the image tag.
- Keep the postgres container's volume on a fast disk. The chat experience
  feels noticeably worse on spinning rust under load.
- Don't share the postgres instance with other applications. The "one DB per
  service" pattern is cheaper than the debugging when something else corrupts
  OWUI's tables.
