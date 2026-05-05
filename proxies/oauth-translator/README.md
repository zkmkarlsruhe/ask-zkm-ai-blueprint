# oauth-translator/

A tiny FastAPI proxy that turns OAuth2 client-credentials into a bearer key.

## Why

Many academic / research clouds expose OpenAI-compatible chat completions but
authenticate with OAuth2 client-credentials (you POST `client_id` + `client_secret`
to a token endpoint and get back a short-lived bearer). LiteLLM only knows
how to send a static bearer key. This proxy bridges the two.

## Wire it up

In `gateway/config.yaml`:

```yaml
- model_name: academic/llama-3.3-70b
  litellm_params:
    model: openai/your-upstream-model-id
    api_base: http://oauth-translator:8080/v1
    api_key: os.environ/INCOMING_BEARER     # the shared secret, NOT the OAuth client_secret
```

In `gateway/.env`, add:

```
INCOMING_BEARER=<same value as in oauth-translator/.env>
```

In `oauth-translator/.env`, fill in your real upstream credentials.

## What this skeleton does not handle

- **Refresh-token flows.** Client-credentials only. If your upstream uses
  authorisation-code with a long-lived refresh token, you need a different
  pattern.
- **Per-user attribution upstream.** This proxy uses one set of credentials
  for everything. Spend attribution stays at LiteLLM's virtual-key layer.
- **Provider-specific quirks.** Some "OpenAI-compatible" upstreams aren't.
  Add the message / model / parameter remapping in the marked section of
  `src/proxy.py`.

## Test

```bash
docker compose up -d
curl -H "Authorization: Bearer $INCOMING_BEARER" http://localhost:8080/v1/models
```
