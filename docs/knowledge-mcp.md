# Central knowledge base as MCP

How the assistant knows your wiki, your website, your collection notes and
your meeting minutes, without anybody uploading files into OpenWebUI.

## The shape

```
 source A (internal wiki)    --+
 source B (collection wiki)  --+--> crawler(s) --> object store (markdown + manifest)
 source C (public website)   --+                            |
 source D (meeting minutes)  --+                            v
                                             ingestor (every minute: new/changed docs)
                                                            |
                                     embeddings via gateway (house/embed)
                                                            v
                                                     vector DB (Qdrant)
                                                            |
                              knowledge service: one MCP endpoint per source
                                 /mcp/<source-a>/   /mcp/<source-b>/   ...
                                                            |
                                     OpenWebUI tool servers, bound per tile
```

- **Crawlers** are small and source-specific (DokuWiki, MediaWiki, a CMS,
  a website via Firecrawl). They write markdown plus a manifest line per
  document (URL, title, updated, source) to an object store. The store is
  the canonical copy; the vector DB can always be rebuilt from it.
- **The ingestor** watches the manifests, chunks new or changed documents,
  embeds them **through the gateway** (so ingest cost lands in the same
  ledger), and writes to Qdrant.
- **The knowledge service** exposes one MCP server per source under its own
  path. Sources are rows in a table (slug, name, description, collection),
  not code: adding a source is a crawler plus a row.
- **OpenWebUI** registers each endpoint as a tool server and binds it only to
  the tiles that should see it.

## Why one endpoint per source

- **Access follows the tile.** Meeting minutes go to the internal tile only;
  the public website can go everywhere. With one combined index you would
  need per-document ACLs in the retrieval path.
- **The model picks better.** A tool named "search_meeting_minutes" with a
  one-line description of what is in there beats a single "search" that
  returns a mix.
- **Splitting is cheap.** A namespace of the internal wiki that needs a
  narrower audience becomes its own source without re-crawling.

## Why MCP instead of OWUI knowledge collections

Uploaded knowledge collections are snapshots: they are stale the day after
upload, they live inside one OWUI instance, and nobody owns their refresh.
A crawler-fed index is current within minutes, serves every instance and
every other consumer (scripts, artworks) the same way, and keeps the source
system as the place where content is edited.

## Practical rules

- **Embedding alias without fallback.** The ingestor and the query path must
  use exactly the same embedding model. Pin it as a gateway alias that never
  falls back (see [`aliases.md`](aliases.md)). Changing the model means a
  full re-embed into a new collection, then switch.
- **Return sources.** Every hit carries title and URL so the model can cite
  and the user can check.
- **Tool-first prompts.** For tiles that answer from the knowledge base, the
  system prompt says: search first, answer only from results, say so when
  nothing was found. Low temperature. Models that ignore tool results and
  answer from memory will invent biographies; test with questions whose
  answer you know, and swap the base model if needed.
- **Restricted sources stay restricted.** Minutes, HR pages and similar get
  their own source and are bound only to tiles for the right group, ideally
  on providers you trust with internal data.
