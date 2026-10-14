# Identity: login, onboarding, offboarding

The second of the four guarantees: **identity**. Every login goes through
your institution's existing SSO. No second password, no anonymous accounts.

This blueprint does not bundle an identity provider. Any OIDC provider works
(Keycloak, Authentik, Entra ID, Okta, Dex, Google Workspace, ...). The
directory behind it (LDAP, AD) is the IdP's business; OpenWebUI only sees
the OIDC claims.

## The flow

```
Browser            OpenWebUI                     IdP                  gateway
  | GET /             |                            |                     |
  | click "SSO"       |                            |                     |
  |------------------>| 302 /authorize  scope=openid email profile groups
  |  login at the IdP --------------------------->|                     |
  |<---------------------------- 302 /oauth/oidc/callback?code=...      |
  |------------------>| code -> tokens (+ userinfo)|                     |
  |                   |<-- sub, email, name, groups|                     |
  |                   | groups contains an allowed role?                 |
  |                   |   no  -> 403, no account                         |
  |                   |   yes -> create/find account, role user|admin,   |
  |                   |          OWUI groups = claim ∩ existing groups   |
  |<-- session JWT ---|                            |                     |
  | chat              |-- POST /chat/completions (instance key) -------->|
  |                   |   X-OpenWebUI-User-Id/-Email/-Role/-Chat-Id      |
  |                   |                            |  spend row per user |
```

## 1. Register an OIDC client in your IdP

- **Client type**: confidential (has a client secret)
- **Redirect URI**: `https://chat.your-house.org/oauth/oidc/callback`
- **Scopes**: `openid`, `email`, `profile`, `groups`
- **A `groups` claim** in the ID token / userinfo. In Keycloak: client-scope
  mapper "Group Membership", claim name `groups`, "Full group path" off
  (OWUI matches exact strings; `/ai-user` does not equal `ai-user`).

## 2. Decide the groups

| IdP group | OWUI role | OWUI group | Who |
|---|---|---|---|
| `ai-user` | user | ai-user | everyone allowed to use the assistant |
| `ai-expert` | user | ai-expert | more models, more features |
| `ai-guru` | user | ai-guru | everything, incl. commercial image models |
| `ai-admin` | admin | ai-admin | the team running the stack |

Names are yours. Be specific (`ai-user`, not `staff`), so granting access
doesn't touch a person's general directory entry. Who may add people to
`ai-user` is a policy decision of whoever owns the IdP; write down who that
is. Tiers in detail: [`tiers.md`](tiers.md).

## 3. Wire the env vars

In `webui/.env` (mapped to OWUI's names in `webui/docker-compose.yml`):

```bash
ENABLE_OAUTH_SIGNUP=true
OIDC_PROVIDER_NAME=Institution SSO
OIDC_CLIENT_ID=museum-ai
OIDC_CLIENT_SECRET=<from step 1>
OIDC_DISCOVERY_URL=https://sso.your-house.org/realms/main/.well-known/openid-configuration

ENABLE_OAUTH_ROLE_MANAGEMENT=true     # role from the groups claim
OAUTH_ALLOWED_ROLES=ai-user,ai-admin  # gate: no listed group, no account
OAUTH_ADMIN_ROLES=ai-admin
ENABLE_OAUTH_GROUP_MANAGEMENT=true    # OWUI groups follow the claim
```

The compose file also sets `OAUTH_GROUP_CLAIM=groups`,
`ENABLE_OAUTH_GROUP_CREATION=false` (only groups you created in OWUI are
synced, an IdP typo cannot create a new group) and
`OAUTH_MERGE_ACCOUNTS_BY_EMAIL=false` (no silent merge into a local account
with the same email).

## 4. Bootstrap and lock down

1. Before enabling OIDC, create the local admin (first signup).
2. Create the OWUI groups (`ai-user`, `ai-expert`, ...) with exactly the
   names from the claim.
3. Log in through the IdP in a private window; check role and groups.
4. Set `ENABLE_LOGIN_FORM=false`, restart. Keep one local admin as
   break-glass for IdP outages.
5. `ENABLE_SIGNUP=false`. Signup and many other settings are
   PersistentConfig: the DB value wins over env after first start. Check the
   effective value (admin UI, or `GET /api/config`).

## Auto-onboarding

There is no manual onboarding step. On first login:

- allowed group present: account created, role set, OWUI groups synced,
- groups present but none allowed: HTTP 403, no account,
- **no `groups` claim at all**: role management cannot decide and the
  account gets `DEFAULT_USER_ROLE` (`user`). Make sure your IdP always
  sends the claim (an empty list is fine), or set `DEFAULT_USER_ROLE=pending`.

Group membership is re-read **at every login**, not continuously: a group
added in the IdP takes effect on the person's next login.

What a new user sees is decided by per-model grants for their groups; there
is no per-user setup. Write a short first-steps page and link it in the
sidebar.

## Offboarding — the caveat

"People who leave lose access automatically" holds only as far as the
session lifetime allows:

- A person removed from the IdP (or from `ai-user`) cannot log in again.
- **An already issued OpenWebUI session stays valid until its JWT expires.**
  OWUI does not re-check the IdP per request. Default `JWT_EXPIRES_IN` is
  `4w`. If your IdP deactivates leavers once a month, the worst case is
  roughly a month plus the JWT lifetime.
- Mitigations: set `JWT_EXPIRES_IN` to something like `1d` or `7d` (users
  re-login through SSO, usually silent while the IdP session lives), and for
  an urgent case deactivate or delete the user in OWUI directly.
- **Data stays.** Accounts, chats, uploads and vectors of people who left are
  not deleted automatically. Decide a retention rule and implement it (OWUI
  admin API or DB job). Put it in your privacy notice.

A directory MCP that filters deactivated accounts at cache load is a nice
side effect: people who left disappear from the phonebook tool on the next
refresh, independent of OWUI.

## Identity downstream

With `ENABLE_FORWARD_USER_INFO_HEADERS=true` every model and tool call
carries `X-OpenWebUI-User-Id`, `-Email`, `-Name`, `-Role` and
`X-OpenWebUI-Chat-Id`:

- the gateway attributes spend per person (`user_header_mappings`) and tags
  rows with email, role and chat id (`extra_spend_tag_headers`),
- tool servers can scope answers to the asking person (`/me`).

The headers are plain text on the internal network. Keep tool servers and
the gateway off untrusted networks, or use OWUI's signed-JWT variant
(`FORWARD_USER_INFO_HEADER_JWT_SECRET`) where the receiver can verify it.

## Common gotchas

- **The `groups` claim isn't sent by default** in most IdPs. Add the mapper.
- **Email must be unique** across the IdP. Two accounts with the same email
  collide on first login (`EMAIL_TAKEN`).
- **Logout** (OWUI 0.12) sends the browser to the IdP's
  `end_session_endpoint` from the discovery document, so it ends the SSO
  session too. Set `WEBUI_AUTH_SIGNOUT_REDIRECT_URL` for where the IdP
  should send people afterwards, or `OPENID_END_SESSION_ENDPOINT` if your
  IdP's discovery lacks the endpoint.
- **Several IdPs in one house** (a central one for staff, a team one for
  admin tools): document which one guards the assistant. It is easy to
  debug the wrong one.
