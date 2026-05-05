# proxies/ — example wrappers for awkward upstreams

Sometimes the model provider you want to use does not speak plain
OpenAI-compatible HTTP. Maybe it requires OAuth2 client-credentials. Maybe
it needs a per-request transformation. Maybe it's a self-hosted thing that
needs guardrails before LiteLLM sees it.

These are **skeleton patterns**, not working integrations. They show the
shape; you fill in the upstream specifics.

## Three patterns

| Folder | When you need it | Lines |
|---|---|---|
| [`oauth-translator/`](oauth-translator/) | Provider needs OAuth2 client-credentials (typical of academic clouds), but LiteLLM only understands bearer-key auth | ~120 |
| [`local-bridge/`](local-bridge/) | You self-host (Ollama, vLLM, llama.cpp) and want to add request shaping, model aliasing, or hard ceilings before LiteLLM | ~100 |
| [`document-preprocessor/`](document-preprocessor/) | OpenWebUI uploads `.docx` / `.pptx` / `.xlsx` and you want them converted to clean text before they hit your RAG pipeline | ~140 |

## Where they sit

```
                      gateway/ (LiteLLM)
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
     oauth-translator   local-bridge   (direct to upstream
              |              |          if no quirks)
              v              v
       academic cloud    Ollama / vLLM
       (OAuth2 needed)   (self-hosted)


             webui/ (OpenWebUI)
                |  uploads
                v
       document-preprocessor    --->  webui's RAG / knowledge base
       (extract text from
        office files first)
```

The first two are model-provider proxies; LiteLLM points at them as if they
were OpenAI. The third is a content-processing side-service for the upload
path, not the chat-completion path.

## What they do not do

- They do not bundle real provider credentials.
- They do not target a specific academic cloud or commercial provider — every
  one has its own quirks. The skeletons name the place where you'd add them.
- They are not battle-tested. The ZKM production proxies have years of edge
  cases baked in. These are clean starting points; you'll add your own.

## Why this folder exists

In the production ask.zkm.ai stack, three of these patterns are real
services with thousands of lines of provider-specific code. We are not
publishing those — they are wired to a specific academic cloud whose API has
changed three times. What generalises is the *shape*: a small HTTP service
in front of an awkward upstream, doing the minimum translation work. That's
what these skeletons show.
