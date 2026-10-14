"""Document preprocessor — a docling-serve-compatible extraction shim.

OpenWebUI (CONTENT_EXTRACTION_ENGINE=docling) posts every uploaded file to
``{DOCLING_SERVER_URL}/v1/convert/file`` as multipart field ``files`` and
reads ``document.md_content`` from the JSON answer. Clean markdown instead
of raw office bytes is what makes RAG over uploads useful.

Two ways to serve that contract:

1. Run docling-serve itself and point OWUI at it. No code needed.
2. Your extraction runs elsewhere (a provider's document-convert API, a
   GPU box, a different converter) with its own request shape or its own
   key. Then put this shim in between: it speaks docling-serve to OWUI and
   your upstream's API to the other side, and holds the upstream key so
   OWUI never sees it.

Configure with UPSTREAM_CONVERT_URL (+ UPSTREAM_API_KEY). Without an
upstream, the shim only passes plain-text files through, which is enough
to wire up and test the upload path.

Adapt ``_call_upstream`` / ``_extract_markdown`` to your upstream's shape.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile

logger = logging.getLogger("document-preprocessor")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
UPSTREAM_CONVERT_URL = os.getenv("UPSTREAM_CONVERT_URL", "").strip()
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "").strip()
UPSTREAM_TIMEOUT_S = float(os.getenv("UPSTREAM_TIMEOUT_S", "300"))
PLAIN_TEXT_SUFFIXES = {".txt", ".md", ".csv"}

app = FastAPI(title="Document Preprocessor")


def _extract_markdown(payload: dict) -> str:
    """Pull markdown out of the upstream's JSON. Adjust to your upstream."""
    for path in (("document", "md_content"), ("markdown",), ("md_content",), ("text",)):
        node = payload
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, str) and node.strip():
            return node
    raise HTTPException(502, "Upstream answer contained no markdown")


async def _call_upstream(filename: str, body: bytes, content_type: str) -> str:
    headers = {"Authorization": f"Bearer {UPSTREAM_API_KEY}"} if UPSTREAM_API_KEY else {}
    async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_S) as client:
        r = await client.post(
            UPSTREAM_CONVERT_URL,
            files={"document": (filename, body, content_type)},
            headers=headers,
        )
    if r.status_code >= 400:
        logger.warning("upstream %s for %s: %s", r.status_code, filename, r.text[:300])
        raise HTTPException(502, f"Upstream conversion failed with HTTP {r.status_code}")
    return _extract_markdown(r.json())


@app.post("/v1/convert/file")
async def convert_file(files: Annotated[UploadFile, File()]):
    """docling-serve contract: multipart 'files' in, document.md_content out."""
    body = await files.read()
    if len(body) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_SIZE_MB} MB limit")
    filename = files.filename or "upload"

    if UPSTREAM_CONVERT_URL:
        md = await _call_upstream(filename, body, files.content_type or "application/octet-stream")
    elif Path(filename).suffix.lower() in PLAIN_TEXT_SUFFIXES:
        md = body.decode("utf-8", errors="replace")
    else:
        # docling-serve reports failures inside HTTP 200; OWUI surfaces errors[].
        return {
            "status": "failure",
            "errors": [{"error_message": "No UPSTREAM_CONVERT_URL configured"}],
        }

    return {"status": "success", "document": {"filename": filename, "md_content": md}}


@app.get("/health")
async def health():
    return {"status": "ok", "upstream_configured": bool(UPSTREAM_CONVERT_URL)}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5001")))


if __name__ == "__main__":
    main()
