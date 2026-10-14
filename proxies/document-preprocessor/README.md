# document-preprocessor/

A docling-serve-compatible shim: OpenWebUI sends uploads here for text
extraction, the shim forwards them to wherever your real converter runs and
returns markdown.

## Why

When OpenWebUI ingests a `.docx`, `.pptx` or scanned `.pdf` with its
built-in loaders, layout, tables and scanned pages often come out as noise.
A proper converter (docling, an OCR-capable convert API) produces clean
markdown, and RAG over uploads gets dramatically better. Unhandled formats
are worse than noisy: raw RTF markup, for example, gets chunked and embedded
verbatim, poisoning the collection and loading the embedding provider.

## The contract

OpenWebUI with `CONTENT_EXTRACTION_ENGINE=docling` calls:

```
POST {DOCLING_SERVER_URL}/v1/convert/file
     multipart: files=<the upload>, to_formats=md,json, ...
-> 200 {"status": "success", "document": {"md_content": "..."}}
```

Failures are reported inside a 200 with `"status": "failure"` and `errors[]`.

## Do you need this shim?

- **You can run docling-serve** (CPU works, GPU is faster): point
  `DOCLING_SERVER_URL` straight at it. No shim.
- **Conversion runs at a provider or on another box** with its own API shape
  or its own key: run this shim. It speaks docling-serve to OpenWebUI and
  your upstream's API on the other side, and keeps the upstream key out of
  OpenWebUI. This is the reference deployment's setup: an academic cloud's
  document-convert endpoint behind a shim like this one.

Note that this path does not go through the LLM gateway: document
conversion is not an OpenAI-shaped API. Its key and its traffic are a
separate line in your data-flow inventory.

## Configure

```bash
cp .env.example .env
$EDITOR .env      # UPSTREAM_CONVERT_URL, UPSTREAM_API_KEY
docker compose up -d
```

Adapt `_call_upstream` (request shape) and `_extract_markdown` (where the
markdown is in the answer) in `src/proxy.py` to your upstream.

In `webui/` (or the admin UI, Documents):

```
CONTENT_EXTRACTION_ENGINE=docling
DOCLING_SERVER_URL=http://document-preprocessor:5001
```

## Test

```bash
echo "Hello world" > /tmp/test.txt
curl -F "files=@/tmp/test.txt" http://localhost:5001/v1/convert/file
# -> {"status":"success","document":{"filename":"test.txt","md_content":"Hello world\n"}}
```
