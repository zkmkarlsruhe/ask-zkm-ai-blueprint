# Adapting this blueprint to your house

A checklist of what to swap, in roughly the order you'll need to swap it.

## Phase 0 — decide before you build

- [ ] **Sovereignty target.** Which providers are acceptable for your house?
      Local / on-prem only? Academic-cloud only? EU only? Commercial as a
      visible opt-in? This decides which providers and aliases go into the
      gateway, and which fallback chains are allowed (see
      [`aliases.md`](aliases.md)).
- [ ] **Identity provider.** Whatever your institution already uses. If you
      don't have OIDC: this is a bigger project. Get OIDC first.
- [ ] **Single domain or multiple?** The blueprint uses one host per
      component. Many institutions prefer one apex (e.g. `ai.zkm.tech`)
      with subdomains. Both work; pick early.
- [ ] **Hosting.** One docker host with 16-32 GB RAM and 200 GB SSD is
      sufficient for sub-1000-user installs. Add a GPU only if you run local
      models.

## Phase 1 — bring up the floor

- [ ] Generate strong secrets for every `_KEY` and `_PASSWORD`.
      Use `openssl rand -hex 32` for keys, `-hex 24` for passwords.
- [ ] `gateway/`: register **one** model provider under an alias
      (`house/<provider>-<role>`). Verify with
      `curl https://$GATEWAY_DOMAIN/v1/models`.
- [ ] Mint one virtual key for the OpenWebUI instance.
- [ ] `webui/`: bring up, sign in as first user (becomes admin), confirm a
      chat completes against the alias from the step above.
- [ ] Register an embedding alias (no fallback) and set it as
      `RAG_EMBEDDING_MODEL`.

## Phase 2 — identity

- [ ] Register OIDC client in your IdP, with a `groups` claim.
- [ ] Create the groups (`ai-user`, `ai-expert`, `ai-guru`, `ai-admin`) in
      the IdP and, with the same names, in OWUI.
- [ ] Wire env vars in `webui/.env` per [`auth.md`](auth.md).
- [ ] Set default permissions to all off; grant features per group
      ([`tiers.md`](tiers.md)).
- [ ] Test OIDC login in a private browser, one account per tier.
- [ ] Disable local login form. Keep one break-glass admin.
- [ ] Set `JWT_EXPIRES_IN` to match your offboarding expectations.

## Phase 3 — observability

- [ ] Price every gateway deployment, including free ones (shadow prices).
- [ ] `cost-tracker/`: bring up on two hostnames, verify
      `/api/users/costs` returns data on the dashboard host and 404 on the
      public host.
- [ ] Decide and tune your `CO2_PER_1K_TOKENS` factor.
- [ ] Write the carbon page copy in `app/content/carbon_info.yaml`; replace
      every line marked `EDIT`.
- [ ] Bake the carbon badge from `webui/customizations/` into a custom OWUI
      image. Test that the badge appears in chat and updates after messages.

## Phase 4 — house-specific tools (MCPs)

The blueprint ships two example MCPs (hello-world + opac). Build your own
based on what data your house has. Common candidates:

- [ ] **Directory MCP** — fuzzy search over LDAP / Active Directory, plus a
      `/me` endpoint reading the forwarded user email. Pattern:
      `ldap3`/`python-ldap` + `fastmcp`.
- [ ] **Knowledge-base MCP** — wiki, website, minutes: crawlers into one
      central index, one MCP endpoint per source
      ([`knowledge-mcp.md`](knowledge-mcp.md)).
- [ ] **Collection / DAM MCP** — query your collection management or digital
      asset system. Often the most valuable, often the hardest because the
      target system has weird auth.
- [ ] **Catalog MCP** — like `mcps/opac/` if you use BSZ aDISWeb; otherwise
      an adapter to whatever your library system exposes.

For each MCP: copy `mcps/hello-world/`, rename, add the data-source client,
add docker network connection to webui, register in OWUI's tool settings,
bind it to the tiles that need it.

Also optional in this phase: web search ([`web-search.md`](web-search.md))
and document extraction ([`document-extraction.md`](document-extraction.md)).

## Phase 5 — branding

- [ ] House display name, locale (`webui/.env`).
- [ ] Favicon, splash logo, custom CSS — drop into `webui/customizations/brand/`,
      uncomment the `COPY` line in `Dockerfile.example`, rebuild.
- [ ] Sidebar links (privacy notice, documentation, report-a-problem) —
      `webui/customizations/sidebar-links.js`.
- [ ] Carbon page copy in `cost-tracker/app/content/carbon_info.yaml`.

## Phase 6 — operationalise

- [ ] **Backups.** Both Postgres DBs (with `LITELLM_SALT_KEY`), the
      `openwebui_data` volume (or S3 bucket), Qdrant snapshots.
      cost-tracker has no state of its own. Daily is enough.
- [ ] **Monitoring.** LiteLLM exposes `/metrics` for Prometheus. OWUI logs to
      stdout. Wire to whatever you already run.
- [ ] **Updates.** OWUI ships often; LiteLLM ships often. Pin tag and
      digest, bump intentionally, canary on a non-production instance
      first: [`operations.md`](operations.md).
- [ ] **Fleet.** Workshop, exhibition or test instances on the same
      gateway: [`../examples/tenants.md`](../examples/tenants.md).

## Phase 7 — the talk you should give

Once you've been running for three months, give a talk about it. The shape:

1. The four guarantees, in one slide each.
2. What your staff actually does with it (4–5 use cases, screenshots).
3. One architecture slide (the diagram from [`architecture.md`](architecture.md)).
4. Your own usage curve — chats per month, accounts active.
5. Your CO₂ number, live, in front of an audience.
6. Three things other houses can take away.
