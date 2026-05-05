# Security policy

## Supported versions

This repository is a **reference implementation**. Only the `main` branch is
maintained. Tagged snapshots are point-in-time references and do not receive
backported fixes.

The third-party components this blueprint composes (OpenWebUI, LiteLLM,
Qdrant, Redis, Postgres, FastMCP) have their own security trees — for
vulnerabilities in those, file with the respective upstream.

## Reporting a vulnerability

For anything specific to **this** repository (the example code, the compose
files, the docs):

1. **Preferred:** open a [private security advisory](../../security/advisories/new)
   on GitHub. Only the maintainer will see it.
2. **Fallback:** if you cannot use GitHub advisories, email the maintainer.
   The address is on the maintainer's GitHub profile.

Please do not open a public issue for security topics until a fix is
available.

## What's in scope

- Insecure defaults in any of the example compose files or env templates
- Secret material accidentally committed to this repo
- Examples in `docs/` or `proxies/` that would lead a careful reader to
  build something insecure
- Cross-site / injection issues in the cost-tracker FastAPI app or in the
  carbon page template

## What's out of scope

- Vulnerabilities in upstream OpenWebUI / LiteLLM / Qdrant / etc. — report
  upstream
- "You can misconfigure this repo to be insecure" — that is the nature of a
  blueprint; please do open an issue if a default is misleading
- Findings against your own deployment that derives from this blueprint —
  report to your own house's security team
