# cost-tracker/ — per-user spend dashboard + public carbon page

One FastAPI app, two hostnames:

| Host | Path | Audience | Auth |
|---|---|---|---|
| `COST_DOMAIN` | `/` | admin / finance | your reverse-proxy middleware |
| `COST_DOMAIN` | `/api/users/costs` | admin / finance | same |
| `CARBON_DOMAIN` | `/carbon` | the public | none |
| `CARBON_DOMAIN` | `/api/carbon/{user_id}` | the in-chat badge in `webui/` | none |
| `CARBON_DOMAIN` | `/api/carbon/stats/{daily,weekly,monthly}` | the public page (charts) | none |

## Never expose per-user data on a public host

The dashboard and `/api/users/*` return names, emails and spend per person.
The app enforces that they are served **only** when the request's `Host`
equals `DASHBOARD_HOST` (set from `COST_DOMAIN`). On any other host they
return 404; `/` redirects to `/carbon`. If `DASHBOARD_HOST` is empty, the
dashboard is off everywhere. The public router in `docker-compose.yml` also
only forwards the carbon paths. Two independent locks: a typo in one Traefik
rule cannot publish staff spend.

`test_app.py` checks this gate at image build time.

## What it does

- **Cost dashboard**: joins LiteLLM's `LiteLLM_SpendLogs` (`user` column, set
  from the `X-OpenWebUI-User-Id` header) with OpenWebUI's `user` table.
  Columns per person: **invoiced** and **shadow** spend, requests, tokens.
- **Carbon page**: token totals times a configurable `CO2_PER_1K_TOKENS`
  factor (default `0.0004` kg). All copy lives in
  `app/content/carbon_info.yaml`; lines marked `EDIT` are house-specific.
- **Carbon API**: feeds the in-chat badge and the page's charts.

## Currency and shadow prices

Spend is whatever unit your gateway's model prices are in. The reference
deployment prices every deployment in **EUR** (LiteLLM's built-in price map is
USD: override `input_cost_per_token` / `output_cost_per_token` on each
deployment if you want EUR, and convert history once if you switch).

Not every upstream sends an invoice. Academic clouds and self-hosted models
cost nothing per token, which makes the sovereign path look free and the
gateway's total meaningless. The reference deployment gives those
deployments **shadow prices**: what the same model would cost at a hosted
provider (same model elsewhere, else the vendor's list price, else an
estimate). Then:

- `invoiced` = what you actually pay,
- `shadow` = what the free upstreams saved you,
- `total` = invoiced + shadow = the value of what was used.

`SHADOW_API_BASE_RE` (Postgres regex on `api_base`) tells the tracker which
rows are shadow-priced. Empty = everything is invoiced.

## Bring up

```bash
cp .env.example .env
$EDITOR .env                       # COST_DOMAIN, CARBON_DOMAIN, DB URLs
docker network create ai-bus 2>/dev/null
docker compose up -d
```

Visit `https://$CARBON_DOMAIN/carbon` — the carbon page should render.
Visit `https://$COST_DOMAIN/` — the dashboard (put auth in front first).

## Wiring it to gateway/ and webui/

Read access to two databases on the `ai-bus` network:

1. **LiteLLM's Postgres** in `gateway/`, alias `litellm-db`.
2. **OpenWebUI's Postgres** in `webui/`, alias `<STACK>-db`.

Use read-only DB users. If OWUI runs on SQLite, the carbon page and API still
work (they only read LiteLLM's DB); the dashboard cannot resolve names.

## Tuning the CO2 factor

`CO2_PER_1K_TOKENS=0.0004` is a rough midpoint of published estimates for
mixed inference. Defensible; not authoritative. One factor for every model
ignores that a 400B model costs far more per token than a 9B one, and that
grids differ. If you want a better number:

- Local inference: measure GPU draw under load × your grid's gCO₂/kWh ÷ tokens/s.
- Cloud inference: ask the provider for per-region grid intensity and energy per request.
- Mixed: weight per model by its share of traffic.

The page says plainly that this is an approximation. **Honesty about the
number is the design feature.** Fill in the `EDIT` lines before you link the
page publicly; a page with placeholder text undermines the point.

## Notes

- The badge endpoint is public and returns one number for an opaque user
  UUID. If that is too much for your house, put `/api/carbon/{user_id}`
  behind the chat's auth (forward-auth) rather than dropping the badge.
- The dashboard (`app/static/index.html`) is a self-contained jQuery +
  DataTables page. No build step.
