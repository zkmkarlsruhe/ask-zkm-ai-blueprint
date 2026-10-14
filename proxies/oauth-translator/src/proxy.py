"""OAuth2 client-credentials -> bearer-key translator.

Many academic / research clouds expose OpenAI-compatible APIs but require
OAuth2 client-credentials (client_id + client_secret -> short-lived bearer
token), not the long-lived API key that LiteLLM expects.

This proxy:
  1. Listens for any OpenAI-compatible request (chat/completions, embeddings,
     models, ...) on its own /v1/* paths.
  2. Lazily fetches and refreshes an access token from the upstream IdP.
  3. Forwards the request upstream with that token in Authorization.
  4. Streams the response back unchanged.

Point LiteLLM at this proxy with a long-lived token of your choice (e.g. a
shared secret you bake into both .envs) — auth between LiteLLM and this
proxy stays simple.

This is a SKELETON. Replace the marked sections for your specific upstream:
  - the token endpoint
  - the upstream base URL
  - any request transformation if the upstream's models/messages shape
    differs from OpenAI's
"""
from __future__ import annotations

import os
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

# ---- CONFIG (edit / read from env) ---------------------------------------
UPSTREAM_BASE_URL = os.environ["UPSTREAM_BASE_URL"]      # e.g. "https://academic-cloud.zkm.tech/v1"
TOKEN_URL = os.environ["UPSTREAM_TOKEN_URL"]             # e.g. "https://sso.zkm.tech/oauth2/token"
CLIENT_ID = os.environ["UPSTREAM_CLIENT_ID"]
CLIENT_SECRET = os.environ["UPSTREAM_CLIENT_SECRET"]
SCOPE = os.environ.get("UPSTREAM_SCOPE", "")             # provider-specific
SHARED_SECRET = os.environ["INCOMING_BEARER"]            # the token LiteLLM uses to call this proxy

# ---- TOKEN CACHE ---------------------------------------------------------
_token: str | None = None
_expires_at: float = 0.0
_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))


async def get_upstream_token() -> str:
    """Cached OAuth2 client-credentials token. Refreshes 60s before expiry."""
    global _token, _expires_at
    if _token and time.time() < _expires_at - 60:
        return _token

    data = {"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    if SCOPE:
        data["scope"] = SCOPE

    r = await _client.post(TOKEN_URL, data=data)
    r.raise_for_status()
    payload = r.json()
    _token = payload["access_token"]
    _expires_at = time.time() + int(payload.get("expires_in", 3600))
    return _token


# ---- APP -----------------------------------------------------------------
app = FastAPI(title="OAuth Translator Proxy")


def _check_incoming_auth(req: Request) -> None:
    """LiteLLM authenticates to this proxy with a shared bearer secret."""
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ") != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    """Forward any /v1/* call upstream with a fresh OAuth token."""
    _check_incoming_auth(request)

    upstream_url = f"{UPSTREAM_BASE_URL.rstrip('/')}/{path}"
    upstream_token = await get_upstream_token()

    # Strip hop-by-hop headers; replace auth with the upstream token.
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {
        "host", "authorization", "content-length", "transfer-encoding", "connection",
    }}
    headers["authorization"] = f"Bearer {upstream_token}"

    body = await request.body()

    # ---- OPTIONAL: per-request transformation ----------------------------
    # Some upstreams need the model name remapped, system messages folded into
    # the first user message, etc. Do that here, on `body` (after json.loads).
    # ----------------------------------------------------------------------

    upstream_resp = await _client.request(
        method=request.method,
        url=upstream_url,
        params=dict(request.query_params),
        headers=headers,
        content=body,
    )

    # Stream the response back. Works for both streaming and non-streaming
    # OpenAI responses.
    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers={k: v for k, v in upstream_resp.headers.items() if k.lower() not in {
            "content-length", "transfer-encoding", "connection",
        }},
        media_type=upstream_resp.headers.get("content-type"),
    )


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    main()
