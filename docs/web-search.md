# Web search: SearXNG + Firecrawl v2

OpenWebUI's web search has two halves: an **engine** that turns a query into
URLs, and a **loader** that fetches those URLs and turns them into text for
the model. The reference deployment self-hosts both.

| Half | Service | OpenWebUI setting |
|---|---|---|
| engine | SearXNG (metasearch, no API keys, no per-query fees) | `WEB_SEARCH_ENGINE=searxng`, `SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>` |
| loader | Firecrawl v2, self-hosted (headless browser, markdown output) | `WEB_LOADER_ENGINE=firecrawl`, `FIRECRAWL_API_BASE_URL=http://firecrawl-api:3002`, `FIRECRAWL_API_KEY` |

Both are commented in `webui/docker-compose.yml`. They are PersistentConfig:
env seeds a fresh DB, afterwards set them in Admin Panel -> Settings -> Web
Search.

## Firecrawl: v2, no translation proxy

OpenWebUI from **0.9.2** calls Firecrawl's `/v2/scrape` directly. Older
setups ran a small proxy translating OWUI's v1 calls to a v2 server, or ran a
v1-only Firecrawl fork. Both are obsolete: run upstream Firecrawl v2 and
point OWUI at it.

Self-hosting Firecrawl v2 is a multi-container stack (API, workers,
Playwright service, Redis, RabbitMQ, its own Postgres). Follow upstream's
`SELF_HOST.md`. Notes from running it:

- Upstream publishes the auxiliary images mostly as `:latest`; pin them by
  digest.
- Keep it off the public internet. Reachable from the OWUI hosts only (IP
  allowlist or internal network); then app-level auth is optional.
- It fetches pages from your egress IP. Some sites block datacenter IPs or
  headless browsers; expect a share of failed fetches.

## SearXNG

The official image `searxng/searxng` works out of the box. Enable the JSON
output format in `settings.yml` (`search.formats: [html, json]`), because
OWUI requests JSON. Keep it internal; a public SearXNG gets scraped.

## Data path

Web search sends the search query to the engines SearXNG queries, and the
fetched pages come from your IP. The pages then go to the chat model like any
other context. None of this passes the LLM gateway: list it separately in
your data-flow documentation.

## Prompting

Web search makes inputs large: several fetched pages per question. Keep
`WEB_SEARCH_RESULT_COUNT` small (3 to 5), and prefer a dedicated "Web
search" tile with a model that handles long context and tool calls well.
