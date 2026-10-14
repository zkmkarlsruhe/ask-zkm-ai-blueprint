# gateway/ — LiteLLM proxy

The single egress point for everything that costs tokens: chat, title and tag
generation, embeddings, rerank, image generation, speech-to-text,
text-to-speech. OpenWebUI talks to this; this talks to your model providers.
Nothing else does.

## Why this matters

If OpenWebUI talks to OpenAI / Anthropic / your academic cloud directly, you
have no way to:
- attribute spend to a person,
- swap providers without touching every client,
- fall back to a second provider when the first one is down,
- forbid a provider house-wide,
- log what was sent (for incidents) or compute carbon (for transparency).

Putting one gateway in the middle gives you all of those for the cost of one
container. This is the single most load-bearing decision in the whole stack.

## What's here

- `docker-compose.yml` — LiteLLM + Postgres (models, keys, spend logs) + Redis
  (router state for rpm-aware routing).
- `config.example.yaml` — router settings, attribution headers, alias-first
  model stubs for academic, local, and commercial providers.
- `Dockerfile.example` — custom image that bakes in config + hooks with a
  build-time import smoke test.
- `hooks/example_hook.py` — one small, real hook to copy from.
- `.env.example` — secrets + domain. Copy to `.env`, never commit.

## Bring up

```bash
cp .env.example .env
$EDITOR .env                                 # set domain + generate secrets
cp config.example.yaml config.yaml
$EDITOR config.yaml                          # uncomment one provider, minimum
docker network create proxy   2>/dev/null    # if not already present
docker network create ai-bus  2>/dev/null
docker compose up -d
```

Verify:

```bash
curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
     https://$GATEWAY_DOMAIN/v1/models
```

## Attribution: one key per instance, user in a header

Do **not** mint a virtual key per person. Mint one virtual key per consumer
(each OpenWebUI instance, each script, each artwork) and let OpenWebUI tell
the gateway who is asking:

1. webui/: `ENABLE_FORWARD_USER_INFO_HEADERS=true`. OpenWebUI then sends
   `X-OpenWebUI-User-Id`, `-User-Email`, `-User-Name`, `-User-Role` and
   `X-OpenWebUI-Chat-Id` with every model call.
2. gateway: `general_settings.user_header_mappings` maps
   `X-OpenWebUI-User-Id` to the spend row's `user`.
3. gateway: `litellm_settings.extra_spend_tag_headers` writes email, role and
   chat id as tags into every spend row.

Result: one connection in OpenWebUI, per-person spend in
`LiteLLM_SpendLogs`, and spend per key / team for everything that is not a
person. Which models a key may call is the key's model scope; which models a
person sees is decided in OpenWebUI (see [`../docs/tiers.md`](../docs/tiers.md)).

## Aliases, routing, fallbacks

Consumers call stable aliases (`house/academic-chat`), never raw vendor model
names. The alias layer, multi-key fan-out, fallback rules, and why embedding
and rerank never fall back: [`../docs/aliases.md`](../docs/aliases.md).

## Hooks

Real providers have quirks LiteLLM does not handle (yet). The reference
deployment runs a handful of small hooks, all baked into a custom image:

| Kind | Example of what it fixes |
|---|---|
| pre-call compatibility | strip message fields a strict provider rejects; default a param an endpoint requires; route a generic TTS alias to a voice by detected input language |
| post-call usage fix | an embedding API reports only `total_tokens`, so spend would log as 0 (`hooks/example_hook.py`) |
| response shaping | replace a model's rambling after an image generation with one clean sentence |
| observation | read `x-ratelimit-*` response headers and log them, observe-only |
| custom provider | a provider endpoint with a non-OpenAI shape (e.g. image edit), registered via `custom_provider_map` |

Rules that kept them maintainable:

- One concern per hook (or one clearly sectioned file per provider family).
- Each hook documents the upstream bug it works around, with a link, and
  the condition under which it can be deleted.
- Build the image with an import smoke test (`Dockerfile.example`); a broken
  import otherwise disables the whole callback chain at runtime.
- Hooks with pure logic get an assert in the build, not only an import.

## What you provide

| Decision | Where |
|---|---|
| Which providers and aliases to register | `config.yaml` or the admin API |
| Provider API keys | `.env`, or named credentials in the DB |
| Public hostname | `.env` (`GATEWAY_DOMAIN`) and your reverse proxy |
| Budgets | none by default; `max_budget` on a single virtual key where you need a hard cap |

## How it talks to the rest of the stack

- **webui/** points at `https://$GATEWAY_DOMAIN/v1` as its OpenAI endpoint
  with one virtual key per instance.
- **cost-tracker/** reads this stack's Postgres on the `ai-bus` network.
- **Knowledge MCPs** embed their documents through the gateway as well, so
  ingest cost shows up in the same ledger.

## Notes

- **`store_model_in_db: true`** makes models, aliases, credentials and
  fallbacks editable through the admin API without a restart. A model swap
  becomes one API call. The price: that state is in the DB, not in git. Back
  up the DB and `LITELLM_SALT_KEY` together.
- **Master key vs. virtual keys.** Never give the master key to OpenWebUI.
- **Admin UI exposure.** The API has to be reachable for consumers; the
  admin UI does not. Restrict `/ui` to your internal network at the reverse
  proxy, and keep the image current — LiteLLM has had critical pre-auth
  vulnerabilities.
- **Upgrades** apply Prisma migrations on start (`USE_PRISMA_MIGRATE`).
  There is no down-migration: take a `pg_dump` before every bump. See
  [`../docs/operations.md`](../docs/operations.md).
- **No response cache.** The reference deployment does not cache
  completions; chat users expect fresh answers and retries are handled by
  the router.
