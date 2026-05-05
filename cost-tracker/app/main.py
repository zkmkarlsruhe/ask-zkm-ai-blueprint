"""Cost reporter + carbon footprint API.

Two surfaces, one app:
  - /             → dashboard (per-user spend, intended to be access-controlled
                    by your reverse proxy: BasicAuth, IP allowlist, OIDC, ...)
  - /carbon       → public carbon footprint page (no auth)
  - /api/users/*  → spend data API (same access expectations as the dashboard)
  - /api/carbon/* → public carbon data API

The original at ZKM uses two separate hostnames (one protected, one public)
and routes by Host header. This blueprint uses path-based routing instead, so
the same reverse-proxy rule can serve both with different middlewares per
path-prefix. See ../examples/traefik-snippet.yml.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

templates = Jinja2Templates(directory="templates")

costs_router = APIRouter(prefix="/api/users", tags=["costs"])
carbon_router = APIRouter(prefix="/api/carbon", tags=["carbon"])


def get_db_connection(db_url: Optional[str]):
    if not db_url:
        raise HTTPException(status_code=500, detail="Database URL not configured")
    try:
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")


# ---------------------------------------------------------------------------
# Cost dashboard API — joins LiteLLM spend logs with OpenWebUI users.
# ---------------------------------------------------------------------------

@costs_router.get("/costs")
async def get_user_costs(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """Per-user spend for a date range. Defaults to last 7 days."""
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
                    ROUND(SUM(spend)::numeric, 6) AS total_cost_usd,
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
                ORDER BY total_cost_usd DESC
                """,
                (start_date, end_date),
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
            result.append({
                "email": user.get("email", "Unknown"),
                "name": user.get("name", "Unknown"),
                "role": user.get("role", "unknown"),
                "total_cost_usd": float(cost_row["total_cost_usd"]),
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
    """Today's CO2 estimate for one user. Backs the in-chat badge."""
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
async def carbon_page(request: Request, amount: Optional[float] = Query(None)):
    """Public carbon information page. Linked from the in-chat badge."""
    return templates.TemplateResponse(
        "carbon_info.html",
        {
            "request": request,
            "amount": round(amount, 2) if amount is not None else 0,
            "co2_factor": CO2_PER_1K_TOKENS,
        },
    )


@app.get("/")
async def dashboard():
    """Per-user spend dashboard. Protect this with your reverse proxy."""
    return FileResponse("static/index.html")


app.include_router(costs_router)
app.include_router(carbon_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
