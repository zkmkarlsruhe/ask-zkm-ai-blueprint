# opac MCP — example: BSZ aDISWeb library catalog

A working FastMCP server we ship in production at ZKM. It searches the
**BSZ aDISWeb OPAC system** — the regional library service used by ZKM, HfG
Karlsruhe, and many other institutions in Baden-Württemberg, Germany.

This is published as an **example** of what a real MCP looks like in
production. If your house uses the same OPAC system, drop it in. If not, use
it as a reference for what shape a substantial MCP takes (12 tools, session
management, pagination, citation export, ~1700 lines of well-tested code).

## What it does

Searches a HTML-based library catalog by mimicking browser interactions
(httpx + BeautifulSoup, no headless browser needed). Provides an LLM with:

- Free-text and advanced search across title, author, subject, ISBN, etc.
- Pagination (next/previous page)
- Detailed item metadata (full bibliographic data + holdings)
- Sort by relevance, title, author, year
- Citation export in BibTeX, Zotero, EndNote, RIS, etc.

See the source for the full API: `src/opac_mcp/server.py`.

## Run

```bash
docker compose up -d
curl http://localhost:8002/mcp     # should respond
```

## Wire to OpenWebUI

Same pattern as `hello-world/`: connect to OWUI's network, then add
`http://opac-mcp:8000/mcp` in OWUI's tool settings.

## Adapting to a different OPAC system

The data-fetching logic is in `src/opac_mcp/client.py`. Replace `OPACClient`
with a class that talks to your library system (Alma, Koha, Aleph, FOLIO,
Worldcat, ...) and re-export the same shape of `SearchResponse` / `ItemDetail`.
The MCP tool layer in `server.py` should not need to change much.

## Why this is a useful reference

Everything tricky about a production MCP is exercised here:

- Stateful sessions (the OPAC is a JSF-style stateful web app)
- HTML scraping with BeautifulSoup, structured into typed dataclasses
- Pagination across two layers (results pages + item detail navigation)
- Multiple transports for the same data (search → detail → export)
- A streamable HTTP transport that survives long LLM tool-call loops
- Health check, non-root user, multi-stage Docker build, resource limits

If your MCP is more than a one-shot query, you'll need most of these patterns.

## License

MIT — see [LICENSE](../../LICENSE) at the repo root.
