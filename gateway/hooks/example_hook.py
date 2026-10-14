"""Example LiteLLM hook: count embedding tokens when a provider reports only total_tokens.

Some embedding APIs answer with ``usage: {"total_tokens": N}`` and no
``prompt_tokens``. LiteLLM computes embedding cost as
``prompt_tokens * input_cost_per_token``, so every such call is logged with
spend 0 — the gateway looks cheaper than it is.

``async_post_call_success_deployment_hook`` runs before LiteLLM computes the
response cost, so fixing usage here corrects spend, spend-log tokens and the
cost header. For embeddings every token is input: prompt_tokens = total_tokens.

Wire it in config.yaml:
    litellm_settings:
      callbacks: ["example_hook.embedding_usage_fix_hook"]

The module must be importable from the directory that holds config.yaml
(``/app/config`` in Dockerfile.example).
"""
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import EmbeddingResponse


def fix_embedding_usage(response):
    usage = getattr(response, "usage", None)
    if (
        isinstance(response, EmbeddingResponse)
        and usage is not None
        and not usage.prompt_tokens
        and (usage.total_tokens or 0) > 0
    ):
        usage.prompt_tokens = usage.total_tokens
        usage.completion_tokens = 0
    return response


class EmbeddingUsageFix(CustomLogger):
    async def async_post_call_success_deployment_hook(self, request_data, response, call_type):
        return fix_embedding_usage(response)


embedding_usage_fix_hook = EmbeddingUsageFix()
