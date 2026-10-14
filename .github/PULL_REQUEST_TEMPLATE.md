## What this changes

One sentence describing the change.

## Why

What problem does it solve? Link any related issue.

## How tested

- [ ] `make lint` passes
- [ ] Affected docker compose files validate (`docker compose config`)
- [ ] Manually brought up the affected stack and verified the change works

## Scope check

This is a **reference implementation**, not a feature-rich product. Please
confirm:

- [ ] The change does not add institution-specific
      values to the public blueprint
- [ ] No real secrets / hostnames / emails / spend numbers are introduced
- [ ] If adding a new component or pattern, it's small enough that someone
      can read and understand it in 30 minutes
