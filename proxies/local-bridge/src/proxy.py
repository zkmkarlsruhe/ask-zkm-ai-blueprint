"""Local-model bridge — sit in front of self-hosted Ollama / vLLM / llama.cpp.

You usually do not need a proxy in front of Ollama or vLLM — LiteLLM speaks
both natively. You DO want one when you need any of:

  - **Model aliasing.** "model: house/fast" -> route to one of three local
    backends depending on load.
  - **Hard ceilings.** Cap max_tokens, temperature, or context length below
    what the backend would otherwise accept. Useful for a shared appliance.
  - **Request shaping.** Inject or strip a system prompt; redact PII patterns
    before they reach the model; rewrite tool definitions to a dialect the
    backend handles.
  - **Beyond-LiteLLM logging.** Per-request audit trail to your SIEM, not
    just the spend log.

This skeleton implements alias routing + a hard max_tokens cap + a system
prompt prefix as illustration. Replace these with your real rules.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("local-bridge")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# ---- CONFIG (real version: load from yaml or env) ------------------------
MODEL_ALIASES: dict[str, str] = {
    # alias the LLM sees    ->    real model id at the backend
    "house/fast":   "llama3.2:3b",
    "house/smart":  "llama3.3:70b",
    "house/coder":  "qwen2.5-coder:32b",
}

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://ollama:11434/v1")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")              # most local backends ignore this
INCOMING_BEARER = os.environ["INCOMING_BEARER"]

MAX_TOKENS_CEILING = int(os.getenv("MAX_TOKENS_CEILING", "4096"))
SYSTEM_PROMPT_PREFIX = os.getenv("SYSTEM_PROMPT_PREFIX", "")    # e.g. "You speak only English." Empty disables.

_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
app = FastAPI(title="Local Model Bridge")


def _check_auth(req: Request) -> None:
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ") != INCOMING_BEARER:
        raise HTTPException(401, "Invalid bearer token")


def _shape_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the house's request rules. Pure function, easy to unit-test."""
    # Alias the model.
    requested = payload.get("model", "")
    real = MODEL_ALIASES.get(requested, requested)
    if real != requested:
        logger.info("alias %s -> %s", requested, real)
    payload["model"] = real

    # Hard max_tokens ceiling.
    if "max_tokens" in payload:
        payload["max_tokens"] = min(int(payload["max_tokens"]), MAX_TOKENS_CEILING)
    else:
        payload["max_tokens"] = MAX_TOKENS_CEILING

    # Inject system-prompt prefix.
    if SYSTEM_PROMPT_PREFIX:
        msgs = payload.get("messages", [])
        if msgs and msgs[0].get("role") == "system":
            msgs[0]["content"] = SYSTEM_PROMPT_PREFIX + "\n\n" + msgs[0].get("content", "")
        else:
            payload["messages"] = [{"role": "system", "content": SYSTEM_PROMPT_PREFIX}] + msgs

    return payload


@app.get("/health")
async def health():
    return {"status": "ok", "aliases": list(MODEL_ALIASES.keys())}


@app.get("/v1/models")
async def list_models(request: Request):
    """Tell LiteLLM about the *aliases* we expose, not the underlying models."""
    _check_auth(request)
    return JSONResponse({
        "object": "list",
        "data": [{"id": alias, "object": "model", "owned_by": "house"} for alias in MODEL_ALIASES],
    })


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    _check_auth(request)
    payload = json.loads(await request.body())
    payload = _shape_request(payload)
    streaming = bool(payload.get("stream"))

    backend_headers = {"content-type": "application/json"}
    if BACKEND_API_KEY:
        backend_headers["authorization"] = f"Bearer {BACKEND_API_KEY}"

    upstream_url = f"{BACKEND_BASE_URL.rstrip('/')}/chat/completions"

    if streaming:
        async def gen():
            async with _client.stream("POST", upstream_url, json=payload, headers=backend_headers) as r:
                async for chunk in r.aiter_raw():
                    yield chunk
        return StreamingResponse(gen(), media_type="text/event-stream")
    else:
        r = await _client.post(upstream_url, json=payload, headers=backend_headers)
        return JSONResponse(r.json(), status_code=r.status_code)


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8081")))


if __name__ == "__main__":
    main()
