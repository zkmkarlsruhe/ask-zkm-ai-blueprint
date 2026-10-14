# Museum AI Stack — Blueprint

A reference architecture for running a sovereign, transparent, multi-user LLM
assistant in a public institution. Open-source throughout. No vendor lock-in.

This is the stack that powers [ask.zkm.ai](https://ask.zkm.ai) at ZKM Karlsruhe
since October 2025. We are publishing it as a **blueprint** — not a one-click
install. Every piece here is a working pattern; the integration with your
specific identity provider, model providers, and content sources is for you to
do (with notes from us on how).

---

## The four guarantees

This stack is designed around four promises that make it usable without bad
conscience inside a public institution:

1. **Sovereignty.** All traffic to model providers passes through one gateway.
   You decide which providers to register. Default to academic / EU; commercial
   / US is a deliberate, visible choice.
2. **Identity.** Login through your institution's existing SSO. No second
   password, no anonymous accounts. Access and tiers follow IdP groups;
   people who leave lose access at their next login attempt (mind the
   session lifetime, see [`docs/auth.md`](docs/auth.md)).
3. **Cost.** Every token is attributed to a person. Spend is queryable and
   visible, split into what you pay and what free (academic, self-hosted)
   upstreams saved you. No surprise bills.
4. **CO₂.** Token use is converted to a CO₂ estimate, shown in the chat
   interface and on a public page. Tunable factor, honest about its
   approximation.

---

## Architecture

```
            Your SSO                           Model providers
                |                                     ^
                v                                     |
       +---------------------------------+    +-------+--------+
       |   webui/    (OpenWebUI + RAG)   |--->|   gateway/     |
       |   the chat surface              |    |   (LiteLLM)    |
       +---------------------------------+    +-------+--------+
                |                                     |
                | (function calls)                    | (spend logs)
                v                                     v
       +-------------------+              +-------------------+
       |     mcps/         |              |  cost-tracker/    |
       |  your house's     |              |  per-user spend   |
       |  data and tools   |              |  + carbon page    |
       +-------------------+              +-------------------+
```

Five components, five folders, each independently runnable as a docker compose
stack. They find each other through env vars you set — no magic glue.
Everything that costs tokens (chat, embeddings, images, audio) goes through
the gateway; tool calls, web search and document extraction deliberately do
not. Details: [`docs/architecture.md`](docs/architecture.md).

---

## What's in this repo

| Folder | What it is | Status |
|---|---|---|
| [`gateway/`](gateway/) | LiteLLM proxy — the one door outside | Compose, router + attribution config, hooks pattern |
| [`webui/`](webui/) | OpenWebUI + Postgres + Qdrant + Redis (the chat surface), fleet via `include` | Working compose, scrubbed of branding |
| [`mcps/`](mcps/) | Example MCP servers (hello-world + library catalog) | Patterns to copy and adapt |
| [`proxies/`](proxies/) | docling-compatible extraction shim + skeletons for awkward upstreams | Patterns showing how to wrap quirks |
| [`cost-tracker/`](cost-tracker/) | Per-user spend (EUR, invoiced vs. shadow) + public carbon page | Working FastAPI app, sanitised |
| [`docs/`](docs/) | Architecture, aliases, identity, tiers, knowledge MCP, web search, document extraction, operations | Prose for humans |
| [`examples/`](examples/) | Reverse-proxy snippet, Postgres notes, instance fleet | Drop-in references |

What is **not** here, by design:
- No identity provider config (every house has one — bring your own)
- No model-provider integration (register your providers and aliases in the gateway)
- No production secrets, no real spend numbers, no real key material
- No specific reverse-proxy / ACME plumbing (Traefik example only)

---

## Quickstart (for people who want to see it run)

This is the order. You will need to fill in env vars at each step.

```bash
# 0. Shared networks, once.
docker network create proxy; docker network create ai-bus

# 1. The gateway. Register at least one model alias in config.yaml,
#    then mint one virtual key for the chat instance.
cd gateway/
cp .env.example .env
cp config.example.yaml config.yaml
$EDITOR .env config.yaml
docker compose up -d

# 2. The chat surface. Point it at the gateway.
cd ../webui/
./gen-env.sh > .env  &&  $EDITOR .env
docker compose up -d

# 3. (Optional) The cost tracker + carbon page.
cd ../cost-tracker/
cp .env.example .env  &&  $EDITOR .env
docker compose up -d

# 4. (Optional) Add an MCP. Start with hello-world.
cd ../mcps/hello-world/
docker compose up -d
# Then in OpenWebUI: Admin Panel -> Settings -> Integrations -> Tool Servers
# -> add http://hello-world:8000/mcp
```

For real-world deployment (TLS, OIDC, tiers, fleet, upgrades) read
[`docs/wiring.md`](docs/wiring.md), [`docs/adapting.md`](docs/adapting.md)
and [`docs/operations.md`](docs/operations.md).

Versions in this snapshot: OpenWebUI v0.12.0, LiteLLM v1.104.0,
Qdrant v1.19.2, Redis 8.10.2, Postgres 18 (OpenWebUI), FastMCP 4.
See [`CHANGELOG.md`](CHANGELOG.md).

---

## Status & support

This is a **reference implementation**. We maintain it as a snapshot of what
we run in production. We are happy to
answer questions and accept pull requests, but offer no SLA and no support
contract. If your house wants help adapting this, reach out — we are glad to
talk.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Marc Schütze | ZKM Karlsruhe.
