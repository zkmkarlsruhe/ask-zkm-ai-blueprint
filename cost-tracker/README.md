# cost-tracker/ — per-user spend dashboard + public carbon page

Two surfaces, one FastAPI app:

| Path | Audience | Auth |
|---|---|---|
| `/` | admin / finance | put your reverse-proxy middleware in front of it |
| `/api/users/costs` | admin / finance | same |
| `/carbon` | the public | none |
| `/api/carbon/{user_id}` | the in-chat badge in `webui/` | none |
| `/api/carbon/stats/{daily,weekly,monthly}` | the public page (charts) | none |

## What it does

- **Cost dashboard**: joins LiteLLM's `LiteLLM_SpendLogs` with OpenWebUI's
  `user` table to attribute every dollar to a person. Sortable, filterable,
  per-date-range. The IP worth sharing here is the SQL — see `app/main.py`.
- **Carbon page**: takes the same token totals and applies a configurable
  `CO2_PER_1K_TOKENS` factor (default `0.0004`). Renders an honest-by-design
  page that explains the approximation. The factor is editable; the
  approximation language is the point.
- **Carbon API**: feeds the in-chat badge in `webui/customizations/`.

## Bring up

```bash
cp .env.example .env
$EDITOR .env                                 # set COST_DOMAIN + DB URLs
docker network create ai-bus 2>/dev/null
docker compose up -d
```

Visit `https://$COST_DOMAIN/carbon` — the carbon page should render.
Visit `https://$COST_DOMAIN/` — the dashboard (put auth in front first).

## Wiring it to gateway/ and webui/

This app needs **direct read access** to two databases:

1. **LiteLLM's Postgres** (lives in `gateway/`). Already on `ai-bus`. Use the
   docker service name `postgres` and the `POSTGRES_PASSWORD` you set in
   `gateway/.env`.
2. **OpenWebUI's database**. By default OWUI uses SQLite, which means joins
   from outside the container are not possible. To enable per-user spend, you
   need to switch OWUI to Postgres — see
   [`../examples/postgres-vs-sqlite.md`](../examples/postgres-vs-sqlite.md).

If you skip step 2: the carbon page and API still work (they only read
LiteLLM's DB). The dashboard will fail because the user-name join can't run.

## Tuning the CO2 factor

`CO2_PER_1K_TOKENS=0.0004` is a conservative midpoint of published estimates
for a mixed inference workload on modern accelerators in temperate-climate
data centres. Defensible; not authoritative.

If your house wants a more honest number:

- For local / on-prem inference: measure your GPU's draw under load × your
  electricity provider's published gCO₂/kWh ÷ tokens/sec.
- For cloud inference: ask your provider for their per-region grid intensity,
  multiply by their published wattage per inference (rare but increasing).
- For an ensemble: weight each model by its share of your traffic.

The `/carbon` page deliberately calls this out as an approximation — see the
HTML template comments. **Honesty about the number is the design feature.**

## What you provide

| Decision | Where |
|---|---|
| Public hostname | `.env` (`COST_DOMAIN`) |
| Auth in front of `/` | your reverse proxy — see `docker-compose.yml` labels |
| OWUI on Postgres (for the join to work) | `examples/postgres-vs-sqlite.md` |
| The CO2 factor | `.env` (`CO2_PER_1K_TOKENS`) |
| Page copy / branding on `/carbon` | `app/templates/carbon_info.html` (PLACEHOLDERs throughout) |

## Notes

- The original at ZKM uses two separate hostnames (one auth-protected, one
  fully public) and routes by `Host` header. This blueprint uses path-based
  routing so one hostname + path-prefix middleware does the same job. If you
  want two hostnames, add a second router rule in `docker-compose.yml`.
- The Cost Reporter dashboard (`app/static/index.html`) is a self-contained
  jQuery + DataTables page. No build step. Edit it, restart, done.
- The carbon page (`app/templates/carbon_info.html`) is *intentionally*
  unbranded — every visible string is marked `PLACEHOLDER:` so it's obvious
  what to replace for your house.
