# Architecture

```
            Identity Provider                        Model Providers
            (Keycloak / Authentik /                  (academic, local,
             Entra / your IdP)                        commercial)
                    |                                       ^
                    | OIDC                                  | OpenAI-compatible
                    v                                       |
       +---------------------------------+    +-------------+--------------+
       |   webui/  (OpenWebUI + Qdrant   |--->|   gateway/  (LiteLLM)      |
       |   + Redis) — the chat surface   |    |   the one door outside     |
       +--+------------------+-----------+    +-------------+--------------+
          |                  |                              |
          | function calls   | uploads                      | (some providers
          | (MCP)            v                              |  via proxies/)
          v          +-------+----------+                   v
   +------+------+   | proxies/         |       +-----------+----------+
   | mcps/       |   | document-        |       | proxies/             |
   | hello-world |   | preprocessor     |       | oauth-translator     |
   | opac        |   +------------------+       | local-bridge         |
   | your-house  |                              +-----------+----------+
   +-------------+                                          |
                                                            v
                                                       upstream
                                                       providers
                                                            
          gateway/'s spend logs ---> cost-tracker/ ---> public /carbon page
                                                       (no auth, on purpose)
```

## Why this shape

**One gateway** is the load-bearing decision. If you let OpenWebUI hold
provider keys directly, you lose the ability to attribute spend, swap
providers, or log requests for incident response. With one gateway:
- every token is logged with a `user` id (LiteLLM's virtual keys),
- swapping a provider is one config change, not a sweep through every client,
- carbon and cost calculations have one source of truth,
- the auditor's question "what data left this building?" has one answer.

**Two databases**, not one. LiteLLM has its own Postgres (spend, virtual
keys, cache). OpenWebUI has its own (chats, users, knowledge). The
cost-tracker reads both — that join is the IP of the cost system.

**Qdrant + Redis are private to webui.** They don't need to be on the shared
`ai-bus` network. Keep them on `webui_backend` only.

## Networks

| Network | Purpose | Members |
|---|---|---|
| `proxy` | reverse-proxy ingress | webui, gateway, cost-tracker |
| `ai-bus` | inter-stack DB access | gateway-postgres, owui-postgres (if you switched), cost-tracker |
| `webui_backend` | webui's internals | webui, qdrant, redis |
| `backend` (per-stack, internal) | each stack's own DB / cache | private |
| `default` (per-MCP) | each MCP's own | per-MCP |

Create the shared ones once: `docker network create proxy ai-bus`.

## What's NOT shown above

- **Reverse proxy** (Traefik, Caddy, nginx). Required, but not bundled — every
  house has theirs. See [`../examples/traefik-snippet.yml`](../examples/traefik-snippet.yml).
- **TLS / ACME**. Whatever your reverse proxy uses.
- **Backups**. The two postgres volumes and `openwebui_data` are what to back
  up. Qdrant and redis are recoverable; the others are not.
- **Monitoring**. LiteLLM exposes `/metrics`; OWUI's logs are docker-standard.
  Plug into whatever you already run.

## What ZKM runs that this blueprint deliberately omits

The production ask.zkm.ai stack adds, on top of this blueprint:

- a custom OWUI image with carbon badge + house links + ZKM branding
- a knowledge-sync job that ingests our wiki + website into the OWUI Knowledge
  feature, group-scoped
- multiple model proxies in front of `gateway/` for academic-cloud quirks
  (document conversion, image generation, OAuth flows specific to a provider)
- workshop-tenant variants of `webui/` from a forge template

Those are house-specific. The blueprint above is the part that generalises.
