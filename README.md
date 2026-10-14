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
   password, no anonymous accounts. People who leave the institution lose
   access automatically.
3. **Cost.** Every token is attributed to a person. Spend is queryable and
   visible. No surprise bills.
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

---

## What's in this repo

| Folder | What it is | Status |
|---|---|---|
| [`gateway/`](gateway/) | LiteLLM proxy — the one door outside | Blueprint compose + commented config |
| [`webui/`](webui/) | OpenWebUI + Qdrant + Redis (the chat surface) | Working compose, scrubbed of branding |
| [`mcps/`](mcps/) | Example MCP servers (hello-world + library catalog) | Patterns to copy and adapt |
| [`proxies/`](proxies/) | Skeleton wrappers for awkward upstreams (OAuth, local-bridge, doc preprocessor) | Patterns showing how to wrap quirks |
| [`cost-tracker/`](cost-tracker/) | Per-user spend dashboard + public carbon page | Working FastAPI app, sanitised |
| [`docs/`](docs/) | Architecture, wiring, auth, adapting | Prose for humans |
| [`examples/`](examples/) | Reverse-proxy snippet, postgres swap, multi-tenancy | Drop-in references |

What is **not** here, by design:
- No identity provider config (every house has one — bring your own)
- No model-provider integration (register your providers in `gateway/config.yaml`)
- No production secrets, no real spend numbers, no real key material
- No specific reverse-proxy / ACME plumbing (Traefik example only)

---

## Quickstart (for people who want to see it run)

This is the order. You will need to fill in env vars at each step.

```bash
# 1. The gateway. Register at least one model provider in config.yaml.
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
# Then in OpenWebUI: Settings -> Tools -> add http://hello-world:8000/mcp
```

For real-world deployment (TLS, OIDC, Postgres, multi-tenancy) read
[`docs/wiring.md`](docs/wiring.md) and [`docs/adapting.md`](docs/adapting.md).

---

## Status & support

This is a **reference implementation**. We maintain it as a snapshot of what we run in production. We are happy to
answer questions and accept pull requests, but offer no SLA and no support
contract. If your house wants help adapting this, reach out — we are glad to
talk.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Marc Schütze | ZKM Karlsruhe.
