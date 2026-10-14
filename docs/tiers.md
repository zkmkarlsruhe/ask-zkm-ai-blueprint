# Tiers: who sees which models and features

One instance, several levels of access, all driven by IdP groups. No
per-user setup.

## Three tiers plus admin

| Tier (IdP group = OWUI group) | Typical scope |
|---|---|
| `ai-user` | chat, file upload, web search, image generation; a small set of purpose tiles plus a few clearly labelled commercial models |
| `ai-expert` | everything above, plus chat controls (system prompt, parameters, valves), code interpreter, own tool servers; more models |
| `ai-guru` | everything above, plus building: own workspace models, knowledge, prompts and tools, shared with groups; the full model list including models you deliberately restrict |
| `ai-admin` | OWUI role `admin`; bypasses all checks |

Users never see a model list of 40 entries. Purpose tiles with plain names
("General tasks", "Complex tasks", "Internal info", "Images", "Web search",
"Library search") are what most people need; the long tail is for the
people who asked for it.

## How it is enforced: three mechanisms

**1. IdP group -> OWUI group.** `ENABLE_OAUTH_GROUP_MANAGEMENT=true` and
`OAUTH_GROUP_CLAIM=groups` keep OWUI group membership equal to the claim at
every login. `ENABLE_OAUTH_GROUP_CREATION=false`: create the four groups in
OWUI once, by hand; the IdP cannot invent new ones. Promoting a person is a
group change in the IdP, effective at their next login.

**2. Feature permissions per group.** Set the system-wide default
permissions (Admin Panel -> Users -> Groups -> default permissions) to
**all off**. Grant features only through group rows. OWUI combines group
permissions with OR, so the most generous group wins; that is why the
baseline must be off, otherwise every tier inherits everything.

Groups are **parallel, not nested**: a guru is typically in `ai-user` and
`ai-guru`, not in `ai-expert`. Make each higher tier a strict superset in its
own group row, and grant "expert and up" models to both `ai-expert` and
`ai-guru`. Verify with one real member per tier after every change.

Consider keeping off for all tiers: personal API keys (admins mint keys when
needed), any "public" sharing (public means outside your SSO), import/export
of models and tools (configuration stays with the admins).

**3. Per-model grants.** In OWUI a model without an access grant is visible
to admins only. Grant `user/*` read for tiles everyone gets, group read for
tier models. Tool servers are bound per model, so a tile only gets the tools
it needs.

The gateway does **not** enforce tiers: the instance's virtual key is the
upper bound of what OWUI can reach at all. For a model to appear in a tile,
all three gates must open: key scope (gateway), connection model filter
(OWUI), group grant (OWUI).

## Labelling instead of hiding

Where you show commercial (e.g. US) models to everyone, label them. OWUI
connections can carry tags: put each provider family on its own connection
(same gateway, same key, `model_ids` filter) and tag it, e.g. "EU" /
"Non-EU". Keep the tag honest: a fast US-hosted inference provider is not
"private" because it serves an open-weights model.

Hard limits belong where personal data is involved: a tile that injects the
user's own profile or exposes a directory tool runs only on providers you
trust with personal data, enforced by a filter that fails closed on any
other base model.

## What to write down outside the software

The software enforces tiers; it does not decide them. Document:

- who may grant each group (owner in the IdP team),
- what a person must bring for a higher tier (training, signed usage
  policy, team lead approval),
- why a model is restricted to a tier (cost, data path, licence).

Without that, tiers drift into "whoever asked the admin".
