# gateway/ — LiteLLM proxy

The single egress point for all model traffic. OpenWebUI talks to this; this
talks to your model providers. Nothing else does.

## Why this matters

If OpenWebUI talks to OpenAI / Anthropic / your academic cloud directly, you
have no way to:
- attribute spend to a person,
- enforce a budget,
- swap providers without touching every client,
- forbid a provider house-wide,
- log what was sent (for incidents) or compute carbon (for transparency).

Putting one gateway in the middle gives you all of those for the cost of one
container. This is the single most load-bearing decision in the whole stack.

## What's here

- `docker-compose.yml` — LiteLLM + Postgres (spend logs) + Redis (cache).
- `config.example.yaml` — commented stubs for academic, local, and commercial
  providers. Pick what fits your house.
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

## What you provide

| Decision | Where |
|---|---|
| Which providers to register | `config.yaml` |
| Provider API keys | `.env` |
| Public hostname | `.env` (`GATEWAY_DOMAIN`) and your reverse proxy |
| Whether to enable budgets | `config.yaml` (`general_settings.max_budget`) — recommended only after a month of observation |

## How it talks to the rest of the stack

- **webui/** points at `https://$GATEWAY_DOMAIN/v1` as its OpenAI endpoint.
  Each OpenWebUI user gets a virtual key minted by LiteLLM, so spend is
  attributed per person automatically.
- **cost-tracker/** reads from this stack's Postgres on the `ai-bus` network.
  No shared credentials needed beyond the DB password.

## Notes

- **`store_model_in_db: true`** means the model list in `config.yaml` becomes
  editable through LiteLLM's admin UI after first boot. Convenient, but
  remember to keep `config.yaml` in version control as the source of truth.
- **Master key vs. virtual keys.** Never give the master key to OpenWebUI.
  Mint a long-lived virtual key for it from `/key/generate` instead.
- **Cache TTL of 5 minutes** is conservative. Increase if you see lots of
  duplicated debugging-style requests; decrease to zero if any of your users
  expect non-deterministic responses every time.
