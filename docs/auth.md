# Authentication

The second of the four guarantees: **identity**. Every login goes through
your institution's existing SSO. No second password, no anonymous accounts.
People who leave the institution lose access automatically.

This blueprint does not bundle an identity provider. Run whatever you already
have. Below is the wiring pattern for OpenWebUI's OIDC flow — the example
uses **Keycloak**, but Authentik, Entra ID, Okta, Auth0, Google Workspace,
Dex, and any other OIDC provider work the same way.

## The pattern in three steps

### 1. Register an OIDC client in your IdP

Whatever your IdP calls "client" or "application":

- **Client ID**: `museum-ai` (or similar)
- **Client type**: confidential (server-side, has a client secret)
- **Redirect URI**: `https://chat.your-house.org/oauth/oidc/callback`
- **Scopes requested**: `openid`, `email`, `profile`, `groups`
- **Add a `groups` claim** to the ID token. This is how you map institution
  groups to OWUI roles.

Save the **client secret** — you'll need it in step 3.

### 2. Decide your group → role mapping

OpenWebUI has three roles: `admin`, `user`, `pending`. Decide which IdP
groups grant which:

| IdP group | OWUI role | Who |
|---|---|---|
| `ai-admin` | admin | the small team running the stack |
| `ai-user` | user | everyone with normal chat access |
| (none / unmapped) | pending | logged in but no permissions until admin promotes — useful as the default if you don't want a free-for-all |

The exact group names are yours to pick. Be specific (`ai-user`, not just
`staff`) so adding/removing access doesn't require touching a person's
overall directory entry.

### 3. Wire the env vars

In `webui/.env`:

```bash
# Disable local login form once OIDC works (admin can re-enable in emergencies)
ENABLE_LOGIN_FORM=false
ENABLE_SIGNUP=false

# OIDC config
OIDC_PROVIDER_NAME=Keycloak
OIDC_CLIENT_ID=museum-ai
OIDC_CLIENT_SECRET=<from step 1>
OIDC_DISCOVERY_URL=https://sso.your-house.org/realms/main/.well-known/openid-configuration
```

In `webui/docker-compose.yml`, uncomment the OIDC block in the `environment:`
section. The relevant variables:

```yaml
ENABLE_OAUTH_SIGNUP: "true"
OAUTH_PROVIDER_NAME: ${OIDC_PROVIDER_NAME}
OAUTH_CLIENT_ID: ${OIDC_CLIENT_ID}
OAUTH_CLIENT_SECRET: ${OIDC_CLIENT_SECRET}
OPENID_PROVIDER_URL: ${OIDC_DISCOVERY_URL}
OAUTH_SCOPES: openid email profile groups

# Map IdP groups to OWUI roles based on the "groups" claim:
ENABLE_OAUTH_ROLE_MANAGEMENT: "true"
OAUTH_ROLES_CLAIM: groups
OAUTH_ALLOWED_ROLES: ai-user,ai-admin
OAUTH_ADMIN_ROLES: ai-admin
```

Restart webui:

```bash
docker compose up -d --force-recreate open-webui
```

### 4. Bootstrap and lock down

1. Before disabling local login, log in once with the local admin account.
2. Confirm OIDC works by logging in through your IdP in a separate browser.
3. Once OIDC works: set `ENABLE_LOGIN_FORM=false`, restart, verify local
   login is gone.
4. Keep one local admin account around as a break-glass for IdP outages.

## Common gotchas

- **The `groups` claim isn't in the ID token by default** in Keycloak. Add a
  client-scope mapper of type "Group Membership", set the token claim name to
  `groups`, set "Add to ID token" = on. Same idea in other IdPs.
- **Group names with slashes** (Keycloak nests groups under `/`). OWUI's role
  matcher does an exact string match. Use the simplest leaf names possible.
- **Email addresses must be unique** across your IdP. If you run multiple
  realms or merged orgs, two accounts with the same email will collide on
  first login.
- **First OIDC login creates the user as `pending`** if `ENABLE_OAUTH_ROLE_MANAGEMENT`
  is on but the user doesn't match any allowed role. Either widen the groups
  or have an admin promote them.
- **Logout is OWUI-local by default.** Configure `OAUTH_LOGOUT_REDIRECT_URL`
  to your IdP's end-session endpoint if you want SSO-wide logout.

## Why this matters more than it looks

The "people who leave the institution lose access automatically" promise is
load-bearing for any conversation about data sensitivity. Without it, the
question "where is the list of people who can talk to your AI?" has no good
answer. With OIDC plus group-claim mapping, the answer is "the same place as
everyone else's institution access — your IdP".
