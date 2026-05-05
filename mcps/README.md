# mcps/ — example MCP servers

MCP (Model Context Protocol) servers are how you teach the chat surface about
your house: what's in your collection, who's in your directory, what's in
your library catalog, what your wiki knows.

Each MCP runs as a small HTTP service. OpenWebUI calls it; the LLM uses its
tools to answer questions that need real data instead of guesses.

## Two examples

| | What it shows | Lines | Useful as |
|---|---|---|---|
| [`hello-world/`](hello-world/) | The bones: one tool, FastMCP, docker | ~80 | A starter you copy and rename |
| [`opac/`](opac/) | A real working MCP we ship in production: searches a regional library catalog (BSZ aDISWeb) with ~12 tools | ~1700 | A reference for what a "real" MCP looks like — pagination, exports, session management |

The opac example happens to target a specific catalog system used by libraries
in Baden-Württemberg, Germany. The pattern (httpx + BeautifulSoup + FastMCP +
streamable-http transport) generalises to any HTML-scrapable source.

## What other MCPs we run (not shipped here, by design)

To keep this blueprint clean, we did not vendor the MCPs that are wired
specifically to ZKM systems. They exist as patterns you can rebuild for your
own house. See [`../docs/adapting.md`](../docs/adapting.md) for sketches of:

- **directory MCP** — fuzzy search of an LDAP / Active Directory phonebook
- **wiki MCP** — RAG over an internal wiki (Outline, Confluence, MediaWiki)
- **collection MCP** — query against a museum collection / DAM system
- **website MCP** — RAG over your public site's content (events, exhibitions)

Each of those is roughly the shape of `opac/` with the data source swapped.

## Wiring an MCP into OpenWebUI

Once your MCP is up and reachable on the same docker network as OWUI:

1. In OWUI: **Settings → Tools → "+"**
2. URL: `http://hello-world:8000/mcp` (use the docker service name, not localhost)
3. Save. The tool surface appears in any chat where the model supports tools.

## Building your own

Copy `hello-world/` to `mcps/<your-name>/`, rename the package, replace the
example tool with what you need, add deps in `pyproject.toml`. The
`docker-compose.yml` pattern just works.
