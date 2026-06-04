# Auth decision — sandbox credential & context attribution

> **Current design (2026-06-03).** The sandbox is **not an authenticated
> principal inside main**: it holds **no credential at all**, and it **cannot
> author a `Context`** (it cannot fabricate `parent_id` / `user_id`). Main
> restores attribution for sandbox-originated events from a cache of contexts
> it issued; anything it does not recognise becomes an unauthenticated action
> (`user_id=None`).
>
> An earlier design gave the sandbox a scoped websocket token; it was never
> wired up (there is no sandbox→main websocket yet) and was removed. It is kept
> as a [superseded appendix](#appendix--superseded-scoped-token-design) so the
> next attempt has prior thinking to reuse when the websocket transport lands.

## The two properties we want

1. **No standing credential.** Nothing in main needs the sandbox to
   authenticate today — all sandbox↔main traffic rides the private control
   channel (stdio/unix `Channel`), not main's websocket/REST API. So the
   sandbox is handed no token. Carrying an unused credential is pure attack
   surface; the credential is redesigned (scopes included) only when a
   sandbox→main websocket consumer actually exists.

2. **No fabricated attribution.** Only a `context_id` string crosses the wire
   from the sandbox — never a `parent_id` or `user_id`. Main never trusts the
   sandbox to *say* who authored an action; it derives attribution itself.

## Context-id restoration

Sandboxed automations and scripts fire events and change states that carry a
`context_id`. We want the original attribution — e.g. the user who pressed the
button that triggered a sandboxed automation — to survive the round-trip,
without letting the sandbox forge it.

Main keeps a bounded **`context_id → Context` cache** of contexts it has issued
to the sandbox. The cache is **seeded where main hands a context down** — when
main forwards a service call into the sandbox, the real (main-issued,
trusted-timestamp) `Context` is recorded under its id. On any inbound sandbox
message carrying a `context_id` (`state_changed`, `fire_event`, the result of a
sandbox-originated `call_service`):

- **Known id** → return the cached main-owned `Context` verbatim, so the
  original `parent_id` / `user_id` survive.
- **Unknown / expired id** → mint a **brand-new** main-owned `Context`
  (`Context(user_id=None)`, which generates its own fresh id) and cache it under
  the sandbox-supplied id so repeated echoes within one operation map to a
  single stable context.

### Why an unknown id is never adopted

`Context` ids are **ULIDs with an embedded millisecond timestamp**, and
downstream consumers (recorder/logbook ordering) read time out of the id. Main
**cannot trust the sandbox's clock** — a sandbox could craft a ULID to back- or
forward-date an event. So for any id main did not itself issue, main generates
its own ULID with its own clock. The sandbox-supplied string is used **only as a
cache key**, never as the resulting context's identity.

### Bounding — TTL, not size

Entries expire on a **15-minute TTL**. Volume is naturally tiny: only contexts
from main→sandbox **service calls** are cached, and the sandbox echoes them back
within the same operation (seconds), so 15 minutes is generous headroom. A miss
is always safe — it falls to a fresh main context — so expiry only loses
parentage on pathologically delayed echoes, never correctness. Lazy pruning on
each resolve is enough; a count cap is an optional backstop.

## Why `user_id=None` rather than a sandbox user

A genuinely sandbox-originated action was authored by nobody main can name, so
`user_id=None` (a system/unauthenticated action) is the honest shape — the same
shape automations and scripts without a user context already produce. An earlier
design created a per-group system user (`"Sandbox: built-in"`, …) purely to have
*something* to stamp as `user_id`; that user existed for no other reason and was
removed. There is no reason for the sandbox to *be* a user when nothing needs it
to authenticate.

## What this removed from core HA

The sandbox no longer touches the auth layer at all:

- **No `RefreshToken.scopes` field or websocket dispatcher enforcement** — the
  scoped-token mechanism (see appendix) was reverted from
  `auth/models.py`, `auth/__init__.py`, `auth/auth_store.py`, and
  `websocket_api/connection.py`.
- **No sandbox token issuance and no per-group system user** — the
  `components/sandbox/auth.py` helper was deleted entirely; the manager no
  longer mints or passes a `--token`, and the runtime no longer carries one.

The only auth-adjacent code left is the context-id cache, which lives in the
sandbox bridge — not in core HA's auth code.

## Future work (not built)

- **Sandbox→main websocket credential.** When a websocket consumer lands (the
  first candidate is remote/containerised sandboxes), the sandbox will need to
  authenticate to main. Design the credential then — the appendix's scoped-token
  shape is a reasonable starting point, deliberately *not* carried until needed.
- **Group attribution on `Context`.** A richer answer than `user_id=None` would
  be a `Context` that records *which sandbox group* originated an action (useful
  for audit/logbook: "this came from the `custom` sandbox") without pretending a
  sandbox is a user. That needs a new optional core `Context` field and is its
  own design; capture it when audit attribution actually needs it.

---

## Appendix — superseded scoped-token design

> Kept as a historical record. **None of this is in the codebase.** It described
> the credential the sandbox *would* present over a sandbox→main websocket that
> was never wired up. Revisit when that transport lands.

The idea was to give the sandbox a restricted `RefreshToken` rather than a
fully-privileged one. v1 handed the subprocess a normal system-user token and
gated `sandbox/*` websocket commands with a per-process allow-list — which left
two holes: the token could call any non-`sandbox/*` API the system user was
authorised for (escalation), and it could read any state/area/device/entity in
main (data exfiltration). Both were per-command gating bolted onto a
fully-privileged token; the platform itself needed to treat the token as
restricted.

**Mechanism (reverted):** an optional `scopes: frozenset[str] | None` on
`RefreshToken` (`None` = fully privileged, unchanged behaviour), enforced
centrally in the websocket dispatcher via a small helper:

```python
def _scope_allows(scopes: frozenset[str], type_: str) -> bool:
    for scope in scopes:
        if scope.endswith("/"):
            if type_.startswith(scope):
                return True
        elif type_ == scope:
            return True
    return False
```

Two grammar forms, chosen to keep the dispatcher allocation-free: a **prefix
grant** (`"sandbox/"` matches any `sandbox/*` command) and an **exact match**
(`"auth/current_user"`). The intended sandbox grant was
`{"sandbox/", "auth/current_user"}`. Putting `scopes` on `RefreshToken` itself
(rather than a `SandboxAccessToken` subclass) kept the surface to one optional
attribute with no token-type fan-out, and made it reusable by any future scoped
consumer (e.g. an OAuth client scoped to `calendar/*`).

**Data sharing** was to ride alongside as opt-in flags
(`share_states` / `share_entity_registry` / `share_areas`), defaulting on for
`built-in` / `main` and off for `custom` (the most likely attacker vector). That
surface was also removed; the replacement is designed in
[`design-share-states.md`](design-share-states.md).
