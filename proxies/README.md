# proxies/ — wrappers for awkward upstreams

Sometimes a service you want to use does not speak the API its client
expects. These are **skeleton patterns** that show the shape of a small
translation service; you fill in the upstream specifics.

## First: try the gateway

Most model-provider quirks belong in the gateway, not in a proxy in front of
it. LiteLLM handles OAuth-less bearer keys, custom `api_base`s, per-key rate
limits and fallbacks natively, and the rest fits into small hooks or a custom
provider baked into the gateway image (see [`../gateway/`](../gateway/)).
The reference deployment used to run several model proxies in front of the
gateway (media generation, academic-cloud quirks, a search-API translator);
all of them were retired once the gateway handled media routes directly and
OpenWebUI spoke Firecrawl v2. Fewer hops, one place for keys and spend.

Reach for a proxy only when the gateway cannot speak the upstream at all.

## Three patterns

| Folder | When you need it |
|---|---|
| [`document-preprocessor/`](document-preprocessor/) | OpenWebUI's extraction engine expects docling-serve, but your converter is a provider API or another box. **In production use.** |
| [`oauth-translator/`](oauth-translator/) | An upstream needs OAuth2 client-credentials, LiteLLM only does bearer keys |
| [`local-bridge/`](local-bridge/) | Self-hosted backends (Ollama, vLLM, llama.cpp) need shaping or hard ceilings before the gateway sees them |

## Where they sit

```
   webui/ (OpenWebUI)
      |  uploads
      v
   document-preprocessor  --->  convert API / docling box
      |  markdown back
      v
   RAG (embeddings via gateway/)


   gateway/ (LiteLLM)
      |
      +--> oauth-translator --> upstream with OAuth2 client-credentials
      +--> local-bridge     --> Ollama / vLLM
      +--> (everything else directly)
```

## What they do not do

- They do not bundle real provider credentials.
- They do not target a specific provider; every one has its own quirks.
- They are starting points, not battle-tested integrations.
