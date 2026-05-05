#!/usr/bin/env bash
# gen-env.sh — interactive .env generator for the webui/ stack.
#
# Prompts for the few decisions that vary per house, fills the rest with
# random secrets. Run as:  ./gen-env.sh > .env
set -euo pipefail

read -rp "Display name (e.g. 'Acme Museum AI'): " WEBUI_NAME
read -rp "Public URL (e.g. https://chat.acme.org): " WEBUI_URL
read -rp "Default locale [en]: " DEFAULT_LOCALE
DEFAULT_LOCALE=${DEFAULT_LOCALE:-en}

read -rp "Gateway base URL (LiteLLM /v1, e.g. https://api.acme.org/v1): " LITELLM_API_BASE
read -rsp "Gateway virtual key (sk-...): " LITELLM_VIRTUAL_KEY
echo

# Derive WEBUI_DOMAIN from WEBUI_URL.
WEBUI_DOMAIN=$(printf '%s\n' "$WEBUI_URL" | sed -E 's#^https?://##; s#/.*$##')

rand() { openssl rand -hex "$1"; }

cat <<EOF
WEBUI_NAME=$WEBUI_NAME
WEBUI_URL=$WEBUI_URL
WEBUI_DOMAIN=$WEBUI_DOMAIN
DEFAULT_LOCALE=$DEFAULT_LOCALE

ENABLE_SIGNUP=false
ENABLE_LOGIN_FORM=true

LITELLM_API_BASE=$LITELLM_API_BASE
LITELLM_VIRTUAL_KEY=$LITELLM_VIRTUAL_KEY

QDRANT_API_KEY=$(rand 24)
REDIS_PASSWORD=$(rand 24)
WEBUI_SECRET_KEY=$(rand 32)
EOF
