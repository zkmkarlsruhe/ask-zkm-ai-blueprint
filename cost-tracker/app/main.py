"""Cost reporter + carbon footprint API.

Two audiences, one app, two hostnames:

  DASHBOARD_HOST (protected by your reverse proxy: BasicAuth, OIDC, IP allowlist)
    /               -> per-user spend dashboard
    /api/users/*    -> per-user spend API (names, emails, EUR)
    /static/*       -> dashboard assets

  any other host (public, e.g. carbon.example.org)
    /carbon         -> public carbon page
    /api/carbon/*   -> public carbon API (badge + aggregated stats)
    /health

Per-person data is host-gated in the app itself, not only at the reverse
proxy: requests for /, /api/users or /static on any host other than
DASHBOARD_HOST get a 404 (or a redirect to /carbon for "/"). If
DASHBOARD_HOST is unset, the dashboard is off everywhere. A router
misconfiguration therefore cannot publish staff spend on the public host.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import yaml
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Cost & Carbon API")

# Public CORS for the carbon API (no credentials, GET-only).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

LITELLM_DB = os.getenv("LITELLM_DB_URL")
OPENWEBUI_DB = os.getenv("OPENWEBUI_DB_URL")
CO2_PER_1K_TOKENS = float(os.getenv("CO2_PER_1K_TOKENS", "0.0004"))

# The only host that may serve per-person spend. Empty = dashboard disabled.
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "").strip().lower()

# Regex (Postgres ~*, case-insensitive) on the spend row's api_base for
# upstreams that send no invoice: academic clouds, self-hosted models. Their
# deployments carry shadow prices (what the same tokens would cost at a
# hosted provider), so total = invoiced + shadow. Empty = no shadow column.
SHADOW_API_BASE_RE = os.getenv("SHADOW_API_BASE_RE", "").strip() or None

PRIVATE_PREFIXES = ("/api/users", "/static")


def _is_dashboard_host(request: Request) -> bool:
    host = request.headers.get("host", "").lower().split(":")[0]
    return bool(DASHBOARD_HOST) and host == DASHBOARD_HOST


@app.middleware("http")
async def per_person_data_only_on_dashboard_host(request: Request, call_next):
    if request.url.path.startswith(PRIVATE_PREFIXES) and not _is_dashboard_host(request):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return await call_next(request)


def _load_carbon_info_content() -> dict:
    """Load content/carbon_info.yaml once. All page copy lives there."""
    path = Path(__file__).parent / "content" / "carbon_info.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CARBON_INFO_CONTENT = _load_carbon_info_content()
DECIMAL_SEPARATOR = str(CARBON_INFO_CONTENT.get("decimal_separator", "."))


def format_co2(kg: float, sep: str = ".") -> str:
    """Format a CO2 amount in kg (unit of the API and the badge's ?amount=):
    below 1 kg in g, otherwise kg."""
    if kg >= 0.9995:  # would round to "1000 g"
        return f"{kg:.2f} kg".replace(".", sep)
    g = kg * 1000
    if g == 0 or g >= 9.95:
        return f"{g:.0f} g"
    if g < 0.1:
        return f"< 0{sep}1 g"
    return f"{g:.1f} g".replace(".", sep)


templates = Jinja2Templates(directory="templates")

costs_router = APIRouter(prefix="/api/users", tags=["costs"])
carbon_router = APIRouter(prefix="/api/carbon", tags=["carbon"])


def get_db_connection(db_url: str | None):
    if not db_url:
        raise HTTPException(status_code=500, detail="Database URL not configured")
    try:
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}") from e


# ---------------------------------------------------------------------------
# Cost dashboard API — joins LiteLLM spend logs with OpenWebUI users.
# Host-gated: only on DASHBOARD_HOST (see middleware above).
# ---------------------------------------------------------------------------

@costs_router.get("/costs")
async def get_user_costs(
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
):
    """Per-user spend for a date range, split into invoiced and shadow. Defaults to last 7 days.

    Amounts are in the currency of your gateway's model prices (EUR in the
    reference deployment).
    """
    if not start_date or not end_date:
        end = datetime.now()
        start = end - timedelta(days=7)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    litellm_conn = get_db_connection(LITELLM_DB)
    owui_conn = get_db_connection(OPENWEBUI_DB)

    try:
        with litellm_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    "user" AS user_id,
                    COUNT(*) AS total_requests,
                    ROUND(SUM(spend)::numeric, 6) AS total_cost_eur,
                    ROUND(COALESCE(SUM(spend) FILTER (
                        WHERE %s::text IS NOT NULL AND api_base ~* %s::text
                    ), 0)::numeric, 6) AS shadow_cost_eur,
                    SUM(total_tokens)        AS total_tokens,
                    SUM(prompt_tokens)       AS prompt_tokens,
                    SUM(completion_tokens)   AS completion_tokens
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime"::date >= %s
                  AND "startTime"::date <= %s
                  AND "user" IS NOT NULL
                  AND "user" != ''
                GROUP BY "user"
                HAVING SUM(spend) > 0
                ORDER BY total_cost_eur DESC
                """,
                (SHADOW_API_BASE_RE, SHADOW_API_BASE_RE, start_date, end_date),
            )
            costs = cursor.fetchall()

        user_ids = [row["user_id"] for row in costs]
        if not user_ids:
            return []

        with owui_conn.cursor() as cursor:
            cursor.execute(
                'SELECT id, email, name, role FROM "user" WHERE id = ANY(%s)',
                (user_ids,),
            )
            users = {row["id"]: row for row in cursor.fetchall()}

        result = []
        for cost_row in costs:
            user = users.get(cost_row["user_id"])
            if not user:
                continue  # spend rows from users who no longer exist in OWUI
            total = cost_row["total_cost_eur"]
            shadow = cost_row["shadow_cost_eur"]
            result.append({
                "email": user.get("email", "Unknown"),
                "name": user.get("name", "Unknown"),
                "role": user.get("role", "unknown"),
                "total_cost_eur": float(total),
                "invoiced_cost_eur": float(total - shadow),
                "shadow_cost_eur": float(shadow),
                "total_requests": cost_row["total_requests"],
                "total_tokens": cost_row["total_tokens"] or 0,
                "prompt_tokens": cost_row["prompt_tokens"] or 0,
                "completion_tokens": cost_row["completion_tokens"] or 0,
            })
        return result

    finally:
        litellm_conn.close()
        owui_conn.close()


# ---------------------------------------------------------------------------
# Carbon API — public, no auth. Backs the in-chat badge and the public page.
# ---------------------------------------------------------------------------

@carbon_router.get("/{user_id}")
async def get_user_carbon(user_id: str):
    """Today's CO2 estimate for one user id. Backs the in-chat badge.

    Public by design: returns one number for an opaque user UUID, no name,
    no spend. If that is too much for your house, put this route behind the
    same auth as the chat (e.g. forward-auth) instead of removing the badge.
    """
    conn = get_db_connection(LITELLM_DB)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM "LiteLLM_SpendLogs"
                WHERE "user" = %s AND DATE("startTime") = CURRENT_DATE
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        tokens = row["total_tokens"] or 0
        co2_kg = (tokens / 1000) * CO2_PER_1K_TOKENS
        return {"co2_kg": round(co2_kg, 6)}
    finally:
        conn.close()


def _aggregate_stats(group_by_sql: str, range_sql: str, label_key: str):
    """Shared shape for daily / weekly / monthly stats endpoints."""
    conn = get_db_connection(LITELLM_DB)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    {group_by_sql} AS bucket,
                    COUNT(*) AS total_requests,
                    COALESCE(SUM(total_tokens), 0)      AS total_tokens,
                    COALESCE(SUM(prompt_tokens), 0)     AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM "LiteLLM_SpendLogs"
                WHERE "startTime" >= CURRENT_DATE - INTERVAL '{range_sql}'
                  AND "user" IS NOT NULL AND "user" != ''
                GROUP BY bucket
                ORDER BY bucket DESC
                """
            )
            rows = cursor.fetchall()

        out = []
        for row in rows:
            tokens = row["total_tokens"] or 0
            out.append({
                label_key: row["bucket"].strftime("%Y-%m-%d"),
                "total_requests": row["total_requests"],
                "total_tokens": tokens,
                "prompt_tokens": row["prompt_tokens"] or 0,
                "completion_tokens": row["completion_tokens"] or 0,
                "co2_kg": round((tokens / 1000) * CO2_PER_1K_TOKENS, 6),
            })
        return out
    finally:
        conn.close()


@carbon_router.get("/stats/daily")
async def daily_stats():
    """Aggregated daily token usage and CO2, last 30 days."""
    return _aggregate_stats('DATE("startTime")', "30 days", "date")


@carbon_router.get("/stats/weekly")
async def weekly_stats():
    """Aggregated weekly token usage and CO2, last 12 weeks."""
    return _aggregate_stats('DATE_TRUNC(\'week\', "startTime")::date', "12 weeks", "week_start")


@carbon_router.get("/stats/monthly")
async def monthly_stats():
    """Aggregated monthly token usage and CO2, last 12 months."""
    return _aggregate_stats('DATE_TRUNC(\'month\', "startTime")::date', "12 months", "month_start")


# ---------------------------------------------------------------------------
# Pages.
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/carbon")
async def carbon_page(request: Request, amount: float | None = Query(None)):
    """Public carbon information page. Linked from the in-chat badge (?amount= in kg)."""
    valid = amount is not None and math.isfinite(amount) and amount >= 0
    return templates.TemplateResponse(
        request,
        "carbon_info.html",
        {
            "amount": format_co2(amount, DECIMAL_SEPARATOR) if valid else None,
            "co2_factor": format_co2(CO2_PER_1K_TOKENS, DECIMAL_SEPARATOR),
            "content": CARBON_INFO_CONTENT,
        },
    )


@app.get("/")
async def root(request: Request):
    """Dashboard on DASHBOARD_HOST, the public carbon page everywhere else."""
    if _is_dashboard_host(request):
        return FileResponse("static/index.html")
    return RedirectResponse("/carbon")


app.include_router(costs_router)
app.include_router(carbon_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
