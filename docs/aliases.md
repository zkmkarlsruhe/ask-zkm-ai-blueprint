# The alias layer

Providers retire models constantly. If OpenWebUI tiles, scripts and
artworks reference vendor model names, every retirement is an outage plus a
sweep through every consumer. The fix is one indirection in the gateway.

## The rule

**A consumer never references a raw vendor model name.** It calls a stable,
version-less alias in the gateway. When the vendor retires or renames the
model, you repoint the alias. No consumer changes.

Convention: `house/<provider>-<role>`, for example

| Alias | Means |
|---|---|
| `house/academic-chat` | default chat model at the academic cloud |
| `house/academic-reason` | reasoning model at the academic cloud |
| `house/eu-chat` | same role at a commercial EU provider (fallback) |
| `house/us-sonnet` | a commercial US model, visible opt-in |
| `house/embed`, `house/rerank` | embedding and rerank for RAG |
| `house/title-gen` | task model for titles, tags, search queries |
| `house/<artwork>` | one alias per artwork or service with its own budget of trust |

Name the role, not the model. An alias called `house/academic-glm-4` that
now serves a different model is a lie every operator has to remember.

Two layers of naming are useful:

1. **Gateway alias** (`house/academic-chat`) — operator-facing, stable.
2. **OpenWebUI tile** ("General tasks", "Complex tasks", "Internal info") —
   user-facing, named by purpose. Users choose a task, not a model; model
   names in the UI mostly confuse. The tile's base model is a gateway alias.

## Fan-out: several keys behind one alias

Academic clouds often cap each API key at a low request rate. Register the
same upstream model several times under one alias, one row per key, each
with its `rpm`:

```yaml
- model_name: house/academic-chat
  litellm_params: { model: openai/<id>, api_base: ..., api_key: os.environ/KEY_1, rpm: 10 }
- model_name: house/academic-chat
  litellm_params: { model: openai/<id>, api_base: ..., api_key: os.environ/KEY_2, rpm: 10 }
```

With `routing_strategy: usage-based-routing-v2` the router spreads load
according to those budgets, and `num_retries: 2` retries a 429 or timeout
on another row. Six keys at 10 rpm behave like one alias at 60 rpm.

## Fallback chains

When every row of an alias fails, the router tries the next alias in its
fallback chain. A typical sovereign chain:

```
house/academic-chat  ->  house/eu-chat  ->  house/eu2-chat
```

Rules that kept 30+ chains correct:

- **Different provider** at each step (a fallback to the same provider fails
  the same way).
- **Same mode** (chat to chat, image to image).
- **No cycles.**
- **Never cross the sovereignty line silently.** A fallback from an EU
  provider to a US one changes where data goes; if you allow it, it must be
  a documented decision, not a default.
- **Embedding and rerank never fall back.** A different embedding model
  produces vectors in a different space, often with a different dimension.
  A silent fallback corrupts every collection it writes to. Fail loudly.

Audit the chains after every catalog change (script it: list aliases, walk
each chain, check provider, mode, cycles).

## Config file or database

`store_model_in_db: true` lets you change models, aliases, credentials and
fallbacks through the admin API without a restart. The reference deployment
keeps `model_list: []` in git and manages the catalog entirely in the DB.

- Gain: a model swap during a provider incident is one API call.
- Cost: git no longer describes the running catalog. Back up the DB, and
  export the catalog (e.g. `GET /model/info`, router settings) on a schedule
  if you want a reviewable history.

Pick one source of truth per concern and write it down.

## Keys and scopes

One virtual key per consumer: each OpenWebUI instance, each script, each
artwork. Scope each key to the aliases it may call. A chat instance may need
several keys if you want separate ledgers (chat / media / RAG), but never
one key per person: the person comes from the forwarded header.

For a model to be usable in a tile, three gates must all open:

1. the instance's key may call the alias (gateway),
2. the OWUI connection exposes it (connection model filter),
3. the user's group has access to the tile (OWUI per-model grants).

See [`tiers.md`](tiers.md).

## Prices

Give every deployment a price, including the free ones. See
[`../cost-tracker/README.md`](../cost-tracker/README.md) on shadow prices.
