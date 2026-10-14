# Document extraction for uploads

When a user attaches a PDF, Word file or slide deck, OpenWebUI extracts the
text, chunks it, embeds it (through the gateway) and retrieves from it. The
quality of the extraction step decides whether RAG over uploads works.

## Use a docling-compatible engine

Set in `webui/` (or Admin Panel -> Settings -> Documents):

```
CONTENT_EXTRACTION_ENGINE=docling
DOCLING_SERVER_URL=http://<extraction-service>:5001
```

OpenWebUI then posts each upload to `/v1/convert/file` and gets markdown
back, with tables and scanned pages handled by the converter instead of
OWUI's built-in loaders.

Two ways to provide that endpoint:

1. **docling-serve** on your own hardware. CPU works for small volumes, a
   GPU is much faster for scans.
2. **A provider's convert API** (some academic clouds offer one) behind the
   shim in [`../proxies/document-preprocessor/`](../proxies/document-preprocessor/),
   which speaks docling-serve to OWUI and holds the provider key. This is the
   reference deployment's setup.

## Formats the default loaders get wrong

Even with an extraction engine, check the formats your users actually
upload. Examples from production on the built-in path:

- **RTF** had no handler and fell through to the plain-text loader: raw RTF
  control words were chunked and embedded. One 12 MB file became about
  12,000 chunks of markup, polluting the collection and saturating the
  embedding provider. Fix: route `.rtf` through a real converter (or patch
  the loader in your custom image, with a build-time check).
- **ODT** conversion via pandoc failed in the image because its pandoc had
  no embedded data files; `ALLOW_PANDOC_NO_SANDBOX=true` is the supported
  workaround (set in `webui/docker-compose.yml`).

## Data path

Uploaded documents go to the extraction service, and from there possibly to
a provider, outside the LLM gateway. Document that path, and pick the
extraction provider with the same sovereignty criteria as your chat models.
