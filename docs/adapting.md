# Adapting this blueprint to your house

A checklist of what to swap, in roughly the order you'll need to swap it.

## Phase 0 — decide before you build

- [ ] **Sovereignty target.** Which providers are acceptable for your house?
      Local / on-prem only? Academic-cloud only? EU only? Commercial as a
      visible opt-in? This decides what goes in `gateway/config.yaml`.
- [ ] **Identity provider.** Whatever your institution already uses. If you
      don't have OIDC: this is a bigger project. Get OIDC first.
- [ ] **Single domain or multiple?** The blueprint uses one host per
      component. Many institutions prefer one apex (e.g. `ai.house.org`)
      with subdomains. Both work; pick early.
- [ ] **Hosting.** One docker host with 16-32 GB RAM and 200 GB SSD is
      sufficient for sub-1000-user installs. Add a GPU only if you run local
      models.

## Phase 1 — bring up the floor

- [ ] Generate strong secrets for every `_KEY` and `_PASSWORD`.
      Use `openssl rand -hex 32` for keys, `-hex 24` for passwords.
- [ ] `gateway/`: register **one** model provider in `config.yaml`. Verify
      with `curl https://$GATEWAY_DOMAIN/v1/models`.
- [ ] `webui/`: bring up, sign in as first user (becomes admin), confirm a
      chat completes against the model from step above.

## Phase 2 — identity

- [ ] Register OIDC client in your IdP.
- [ ] Wire env vars in `webui/.env` per [`auth.md`](auth.md).
- [ ] Test OIDC login in a private browser.
- [ ] Disable local login form. Keep one break-glass admin.

## Phase 3 — observability

- [ ] `cost-tracker/`: bring up, verify `/api/users/costs` returns data.
- [ ] If you want per-user names in the dashboard, switch OWUI to Postgres
      ([`../examples/postgres-vs-sqlite.md`](../examples/postgres-vs-sqlite.md)).
- [ ] Decide and tune your `CO2_PER_1K_TOKENS` factor.
- [ ] Customise `app/templates/carbon_info.html` — every visible string is
      marked `PLACEHOLDER:` and is yours to write.
- [ ] Bake the carbon badge from `webui/customizations/` into a custom OWUI
      image. Test that the badge appears in chat and updates after messages.

## Phase 4 — house-specific tools (MCPs)

The blueprint ships two example MCPs (hello-world + opac). Build your own
based on what data your house has. Common candidates:

- [ ] **Directory MCP** — fuzzy search over LDAP / Active Directory. Pattern:
      `python-ldap` + `fastmcp`. ~200 lines.
- [ ] **Wiki MCP** — search over your internal wiki. Pattern depends on the
      wiki: Outline has an API, Confluence has REST, MediaWiki has the action
      API. Either query directly each turn, or pre-index into Qdrant and
      query that.
- [ ] **Collection / DAM MCP** — query your collection management or digital
      asset system. Often the most valuable, often the hardest because the
      target system has weird auth.
- [ ] **Public-website MCP** — scrape your own site (Drupal, WordPress,
      Wagtail, ...) into a structured search.
- [ ] **Catalog MCP** — like `mcps/opac/` if you use BSZ aDISWeb; otherwise
      an adapter to whatever your library system exposes.

For each MCP: copy `mcps/hello-world/`, rename, add the data-source client,
add docker network connection to webui, register in OWUI's tool settings.

## Phase 5 — branding

- [ ] House display name, locale (`webui/.env`).
- [ ] Favicon, splash logo, custom CSS — drop into `webui/customizations/brand/`,
      uncomment the `COPY` line in `Dockerfile.example`, rebuild.
- [ ] Sidebar links (privacy notice, documentation, report-a-problem) —
      `webui/customizations/sidebar-links.js`.
- [ ] Carbon page copy in `cost-tracker/app/templates/carbon_info.html`.
      Replace every `PLACEHOLDER:` string.

## Phase 6 — operationalise

- [ ] **Backups.** What to back up: gateway/postgres volume, webui/openwebui_data
      volume, cost-tracker has no state of its own. Daily is enough.
- [ ] **Monitoring.** LiteLLM exposes `/metrics` for Prometheus. OWUI logs to
      stdout. Wire to whatever you already run.
- [ ] **Updates.** OWUI ships often; LiteLLM ships often. Pin versions, bump
      intentionally, test in a staging tenant first if you have one.
- [ ] **Multi-tenancy.** If you want workshop / training tenants on the same
      hardware, see [`../examples/tenants.md`](../examples/tenants.md).

## Phase 7 — the talk you should give

Once you've been running for three months, give a talk about it. The shape:

1. The four guarantees, in one slide each.
2. What your staff actually does with it (4–5 use cases, screenshots).
3. One architecture slide (the diagram from [`architecture.md`](architecture.md)).
4. Your own usage curve — chats per month, accounts active.
5. Your CO₂ number, live, in front of an audience.
6. Three things other houses can take away.

That talk is what convinced ZKM's sister institutions that this was worth
copying. It's also why this blueprint exists.
