# opac MCP — example: aDISWeb library catalog

A working FastMCP server derived from one we run in production. It searches
**aDISWeb OPAC** catalogs, the system behind the BSZ/IBS regional library
service used by many libraries in Baden-Württemberg, Germany.

Published as an **example** of what a real MCP looks like. If your library
uses aDISWeb, configure it and drop it in. If not, use it as a reference for
the shape a substantial MCP takes (12 tools, session management, pagination,
citation export).

## Configure for your catalog

Everything institution-specific comes from env (see `docker-compose.yml`).
The defaults are placeholders and do not reach a real catalog.

| Variable | What | Example |
|---|---|---|
| `OPAC_BASE_URL` | the aDISWeb app URL | `https://bsz.ibs-bw.de/aDISWeb/app` (BSZ-hosted catalogs) |
| `OPAC_PROFILE` | your catalog profile: the `sp=` value in your OPAC's start link | `SOPACnn` |
| `OPAC_CATALOG_NAME` | how the model should name the catalog | `Library of the Example Museum` |
| `OPAC_CATALOG_FOCUS` | one phrase on what the collection holds | `art, media art and design literature` |

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
OPAC_BASE_URL=... OPAC_PROFILE=... docker compose up -d
curl http://localhost:8002/health     # -> ok
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
- Health route, non-root user, multi-stage Docker build, resource limits

## Lessons from production

- **Fewer tools beat more tools.** With every tool exposed, models
  got lost and one question triggered 16 to 24 catalog fetches. Bind only the
  tools a tile needs, or wrap the common path in one or two coarse tools
  (search + item), and give the tile a system prompt that says when to stop.
- **Live availability is the point.** Pre-indexed metadata is fine for
  semantic search; loan status has to come from the live catalog.

If your MCP is more than a one-shot query, you'll need most of these patterns.

## License

MIT — see [LICENSE](../../LICENSE) at the repo root.
