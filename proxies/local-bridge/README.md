# local-bridge/

A FastAPI shim in front of a self-hosted LLM backend (Ollama, vLLM, llama.cpp).
Adds three things LiteLLM can't easily do on its own:

1. **Model aliasing.** Expose `house/fast`, `house/smart`, `house/coder` —
   what the LLM actually runs is your decision, not the user's.
2. **Hard ceilings.** Cap `max_tokens` regardless of what the client asks
   for. Saves a lot of self-inflicted trouble on shared appliances.
3. **Request shaping.** Prefix a system prompt, rewrite tool definitions,
   redact PII patterns before the model sees them.

## When you don't need this

If you just want to expose Ollama or vLLM to LiteLLM with default behaviour,
LiteLLM speaks both natively. Skip this proxy.

## Wire it up

In `gateway/config.yaml`:

```yaml
- model_name: house/fast
  litellm_params:
    model: openai/house/fast              # the alias the bridge knows
    api_base: http://local-bridge:8081/v1
    api_key: os.environ/LOCAL_BRIDGE_KEY

- model_name: house/smart
  litellm_params:
    model: openai/house/smart
    api_base: http://local-bridge:8081/v1
    api_key: os.environ/LOCAL_BRIDGE_KEY
```

In `gateway/.env`:

```
LOCAL_BRIDGE_KEY=<same value as INCOMING_BEARER in local-bridge/.env>
```

## Customise

The interesting code is `_shape_request()` in `src/proxy.py`. Add your own
rules there — they execute before the request reaches the backend. Keep it
pure (no I/O) so you can unit-test it.

The interesting config is `MODEL_ALIASES` at the top of `src/proxy.py`.
Move it to a yaml file for a real deployment.

## Test

```bash
docker compose up -d
curl -H "Authorization: Bearer $INCOMING_BEARER" http://localhost:8081/v1/models
# -> {"object":"list","data":[{"id":"house/fast",...},{"id":"house/smart",...},...]}
```
