# mcps/ — example MCP servers

MCP (Model Context Protocol) servers are how you teach the chat surface about
your house: what's in your collection, who's in your directory, what's in
your library catalog, what your wiki knows.

Each MCP runs as a small HTTP service (streamable HTTP transport). OpenWebUI
calls it directly as a tool server; the gateway is not in that path. The LLM
uses its tools to answer questions that need real data instead of guesses.

## Two examples

| | What it shows | Useful as |
|---|---|---|
| [`hello-world/`](hello-world/) | The bones: two tools, FastMCP 4, docker | A starter you copy and rename |
| [`opac/`](opac/) | A real MCP derived from production: searches an aDISWeb library catalog with ~12 tools | A reference for sessions, pagination, exports, health route |

Both target `fastmcp>=4`. The pattern (httpx + a parser + FastMCP +
streamable-http) generalises to any source you can query.

## Patterns we run but do not ship

Wired to house systems, so not vendored. Each is a pattern you can rebuild:

- **Directory MCP** — fuzzy search over LDAP / Active Directory (nicknames,
  umlauts, abbreviations, reverse phone lookup). Keep an in-memory cache of
  active people and filter deactivated and service accounts out at load
  time. Add a **`/me` endpoint** that reads the `X-OpenWebUI-User-Email`
  header OpenWebUI forwards (`ENABLE_FORWARD_USER_INFO_HEADERS=true`) and
  returns the asking person's own profile. A small OpenWebUI filter can
  inject that profile into the system prompt of one specific model, so
  "my department" and "who am I" work. Bind personal-data tools and that
  filter only to models on providers you trust with personal data, and make
  the filter fail closed when the base model is anything else.
- **Knowledge-base MCP** — one central service, one MCP endpoint per source
  (internal wiki, collection wiki, public website, meeting minutes). See
  [`../docs/knowledge-mcp.md`](../docs/knowledge-mcp.md).
- **Collection / DAM MCP** — query a collection management system or media
  archive. Often the most valuable, often the hardest (auth).

## Wiring an MCP into OpenWebUI

Once your MCP is up and reachable on a docker network OWUI is on:

1. In OWUI: **Admin Settings → External Tools → "+"**, type MCP (streamable HTTP)
2. URL: `http://hello-world:8000/mcp` (docker service name, not localhost)
3. Save. Then bind the tool server to the models that should use it
   (Workspace → Models → Tools). Global tools on every model confuse models
   and leak data paths you did not intend.

Tool-server connections are runtime config in OWUI's DB, cached in Redis.

## Building your own

Copy `hello-world/` to `mcps/<your-name>/`, rename the package, replace the
example tools, add deps in `pyproject.toml`. Add a `/health` custom route
(see `opac/`) so the container can report healthy. Keep the tool surface
small: a model with five well-described tools beats one with fifteen.
