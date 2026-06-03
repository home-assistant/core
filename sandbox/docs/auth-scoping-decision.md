# Auth-scoping decision (Phase 7)

> **SUPERSEDED 2026-06-03 by `plans/plan-strip-auth-scopes.md`.** No
> consumer of this mechanism ever shipped (the sandbox→main WebSocket was
> not wired up). The `RefreshToken.scopes` field and dispatcher
> enforcement were reverted from core HA; the sandbox now uses a plain
> system-user token. The design below is preserved as a historical record
> so the next attempt (when the WS transport actually lands) has prior
> thinking to reuse.

> **Decision:** sandbox tokens are scoped `RefreshToken`s. The
> `scopes` set lives on `RefreshToken` itself (no subclass, no new
> token type); the websocket dispatcher enforces it per command via a
> shared `_scope_allows` helper. The scope set granted to sandbox
> tokens is `{"sandbox_v2/", "auth/current_user"}` — one prefix grant
> for the full sandbox namespace plus a single exact-match entry so
> the runtime can confirm which user it authenticated as. Opt-in
> data sharing rides alongside the scope set as
> `SandboxGroupConfig.share_states / share_entity_registry /
> share_areas`, default off everywhere, default on for `built-in`
> and `main`.

The plan called Phase 7 "the riskiest from a security review angle"
and asked for a separate review by someone outside the sandbox work
([`plan.md`](../plan.md), "Risks → Auth scoping is a security
boundary"). This doc captures what shipped, what it replaced from v1,
and what's owed before the sharing knobs are turned on.

## What v1 did and why it wasn't enough

v1's `sandbox` integration ([`../sandbox/OVERVIEW.md`](../../sandbox/OVERVIEW.md))
created a system user per sandbox and handed the subprocess a normal
access token issued from a normal refresh token. The `sandbox/*`
websocket commands each called `connection.refresh_token_id` against
a per-process allow-list to gate their own dispatch.

That left two holes both flagged explicitly in v1's "Known
Limitations":

- **Auth boundary** — the sandbox token grants any non-`sandbox/*`
  websocket/REST API the system user is authorised for. A
  compromised integration inside the sandbox can escalate out of
  "sandbox-only" and act against the host (call `light.turn_on`
  arbitrarily, query state, sign download URLs, etc.).
- **Data isolation** — the same token also reads any state, area,
  device, or entity in main. A misbehaving integration can
  exfiltrate data from unrelated integrations.

Both were fundamentally per-command gating bolted onto a
fully-privileged token. v2 needed a token that the platform itself
treats as restricted, with the restriction checked centrally.

## Options considered

### Option 1: a `SandboxAccessToken` subclass of `RefreshToken`

The plan's first draft. A new token type whose `is_valid` /
`token_type` is recognised by the websocket layer; the dispatcher
special-cases the subclass.

- Pro: the type itself encodes "this is locked-down".
- Con: token-type fan-out everywhere — `auth/__init__.py`,
  `auth_store.py`, places that switch on `TOKEN_TYPE_*`. Each new
  use case ("a long-lived sandbox token for plug-in development", "a
  test fixture that wants the same scope") gets its own subclass.
- Con: token type and the *thing it restricts* are orthogonal. A
  future "OAuth client scoped to `calendar/*`" would want the same
  shape but isn't a sandbox.

### Option 2: a `scopes` attribute on `RefreshToken` itself

What we shipped. `RefreshToken` grows an optional
`scopes: frozenset[str] | None` field; `None` means "fully
privileged" (today's behaviour). Any non-`None` value is enforced by
the dispatcher.

- Pro: small surface — one optional attribute, one shared enforcement
  helper, no new types or migration.
- Pro: reusable. The sandbox is the first consumer; nothing about
  the mechanism is sandbox-specific.
- Pro: backwards-compatible by construction. Every existing token
  loads with `scopes=None` and behaves exactly as before.
- Con: anyone calling `auth.async_create_refresh_token(...)` can
  now create a scoped token. The risk is bounded — call sites need
  explicit code to set `scopes`, and the dispatcher's default is
  "no restriction" when `scopes is None" — but the surface is open.

The plan's open question 1 — *"Should the sandbox token's scopes
mechanism be a general HA feature or a sandbox-private one? Lean
general."* — answered itself once we realised Option 1's subclass
explosion was the wrong shape.

## What shipped

### Core surface

`homeassistant/auth/models.py:126-134` — `RefreshToken` grows
`scopes: frozenset[str] | None = None`. The dataclass default
preserves today's behaviour for every existing token.

`homeassistant/auth/__init__.py:453-518` —
`AuthManager.async_create_refresh_token` accepts and forwards
`scopes` to the store. All other call sites are unchanged.

`homeassistant/auth/auth_store.py:204-235, 478-500, 561-587` —
`AuthStore.async_create_refresh_token` accepts `scopes`; the
persisted dict carries `scopes` as a sorted list (so the on-disk
shape is stable across reloads); reload uses `dict.get("scopes")` so
pre-existing stored tokens load with `scopes=None`. **No storage-
version bump** is needed — the new key is optional on read.

`homeassistant/components/websocket_api/connection.py:43-62, 79-90,
232-245` — `ActiveConnection` stores `scopes` from the refresh
token; `async_handle` checks each incoming command type via the
module-level `_scope_allows` helper and rejects with
`ERR_UNAUTHORIZED`. Unscoped tokens (`scopes is None`) skip the
check entirely.

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

### Scope grammar

Two forms, chosen to keep the dispatcher fast (no regex, no
per-message allocation):

- **Prefix grant** — an entry ending in `/` matches any command
  whose type starts with that prefix. `"sandbox_v2/"` permits every
  `sandbox_v2/*` command without listing them individually. This is
  the form sandbox tokens use for their namespace.
- **Exact match** — any other entry must equal the command type
  verbatim. `"auth/current_user"` lets the runtime call exactly
  that one command.

The grammar is intentionally minimal. No wildcards, no negation, no
nesting. If a future consumer needs richer matching, the helper is
the one place to extend; nothing about the on-disk shape forces a
choice now.

### Sandbox-side issuance

`homeassistant/components/sandbox_v2/auth.py` is the sandbox-private
helper. The contract:

- One **dedicated system user per group** (`"Sandbox v2: built-in"`,
  `"Sandbox v2: custom"`, `"Sandbox v2: main"`). System users are
  the right shape — they're not displayable in the frontend, they
  don't have a password, and they already exist for similar
  internal-token use cases.
- One **scoped refresh token per group**, identified by matching the
  `scopes` set against `SANDBOX_TOKEN_SCOPES`. Lookup-or-create on
  each call: HA restarts hand the subprocess the same token it had
  before.
- The CLI access token the manager passes via `--token` is freshly
  created from the refresh token on each call, so restart-rotation
  *of access tokens* is free; the refresh token is stable (see
  "Trade-offs" below).

The scope set is a `frozenset` so it can serve as a dictionary key
in the dispatcher path and so the auth store's serialisation
(`sorted(refresh_token.scopes)` → list → frozenset on load) is
deterministic.

### Sharing knobs

Auth-scope-as-deny ("can't call X") is paired with a positive opt-in
for shared *data*. The plan's open question 2 asked whether to
default `share_states` to True for `built-in` (matching v1) or False
everywhere (locked-down). Answered: **default per group**, surfaced
via `SandboxGroupConfig` + `DEFAULT_GROUP_CONFIGS` in
`manager.py`:

| Group | `share_states` | `share_entity_registry` | `share_areas` |
|---|---|---|---|
| `main` | True | True | True |
| `built-in` | True | True | True |
| `custom` | False | False | False |

The CLI accepts `--share-states` / `--share-entity-registry` /
`--share-areas`; the runtime stores them on a `SharingConfig`
dataclass that the future subscription consumer will read.

`custom` defaulting to all-off is the more conservative choice and
matches the threat model — a custom (HACS) integration is the most
likely vector for an attacker, and a custom integration that *needs*
to see main's state can opt in explicitly by overriding
`group_configs=` when the integration starts.

## Trade-offs worth recording

- **The refresh token is stable across HA restarts.** Once
  `_get_or_create_sandbox_refresh_token` finds a token whose scope
  set matches `SANDBOX_TOKEN_SCOPES`, it reuses it. The access
  token is regenerated on every issuance, but the refresh token's
  long-lived secret persists in the auth store. The docstring calls
  this out as "rotate the refresh token on each call" being
  aspirational — once the sandbox→main websocket connection ships,
  the call has to choose: keep the stable token (simpler, matches
  every other system-user token in HA) or rotate per spawn (tighter
  blast radius if a subprocess is compromised but a connection
  remains open). We deferred the rotation choice to the same PR
  that wires the websocket.
- **The `scopes` field is open to any caller.** Anyone with access
  to `auth.async_create_refresh_token` can mint a scoped token. The
  risk is bounded — only explicit code paths set `scopes`, the
  default is permissive, and the field isn't user-facing in the
  frontend — but a future hardening pass might want a separate
  `auth.async_create_scoped_refresh_token` helper that's the only
  caller allowed to set the field. Not blocking for v2.
- **Scope checks are O(scopes) per command.** Sandbox tokens carry
  two entries, so two comparisons per dispatch — not measurable.
  If a future consumer ships a token with hundreds of exact-match
  entries, the helper would want a hash-set fast path with prefix
  matching as fallback. Cross that bridge later.
- **Scope set serialisation is JSON-sorted.** The auth store writes
  `sorted(refresh_token.scopes)` so the on-disk shape is stable
  across reloads; load reconstructs a `frozenset`. The dispatcher
  comparison is set-based, so order doesn't leak into behaviour.
- **No supervisor/instance collision handling.** Two HA processes
  (e.g. dev and prod) sharing the same auth store would each create
  their own `Sandbox v2: built-in` user with the same name. Same
  shape as the existing supervisor user collision pattern — not new
  in v2 — but worth noting if multi-instance auth stores ever land.
- **`_client_id_for_group` exists but isn't used.** Kept for the
  case where the rotation-on-each-call story flips and the refresh
  token needs a stable `client_id` for dedupe. Wire it in if/when
  that decision changes.

## What's deferred

- **The sandbox→main websocket connection.** The token + share flags
  are wired through to the runtime today, but the runtime does not
  open a websocket back to main. The locked-down posture is
  enforced trivially (no subscription code exists) and asserted by
  `test_sandbox_runtime.test_runtime_starts_in_locked_down_sharing_posture`.
  Phase 8's `RemoteStore` is the first piece that needs the
  connection; when that lands, opening it and subscribing (gated on
  `sharing.share_states`) is a straight extension of the runtime's
  `run()` setup.
- **`share_states=True` filtering on main.** The plan called for
  "main's `subscribe_events` and state reads filter to data the
  sandbox is allowed to see" when sharing is on. The config knob is
  in place but the filtering side hasn't shipped — it should land
  in the same PR as the subscription. The natural place to gate
  this is `_scope_allows` plus a per-event scope check on the
  subscription's emit path.
- **Frontend surfacing of the knob.** `SandboxGroupConfig` is not
  user-facing in v2 — to lock down `built-in` today, you override
  `group_configs=` in code. Phase 11+ follow-up.
- **Token rotation on subprocess respawn.** See the trade-off
  above. Decide alongside the websocket-connection PR.

## Tests landed

| Test | What it asserts |
|---|---|
| `tests/components/sandbox_v2/test_auth.py` | The issuance helper creates exactly one system user per group, reuses the matching refresh token, and stamps the right scope set on the resulting token. |
| `tests/components/websocket_api/test_scopes.py` | A scoped token is rejected (`Unauthorized`) for an out-of-scope command (`light.turn_on`); accepted for `sandbox_v2/*`; rejected for `auth/sign_path`; accepted for `auth/current_user`. |
| `tests/auth/test_init.py` | Scoped refresh tokens round-trip through the auth store (sorted-list on disk, frozenset on load). Pre-existing tokens without the `scopes` key load as `scopes=None`. |
| `sandbox_v2/hass_client/tests/test_sharing_config.py` | `SharingConfig` parses the `--share-*` CLI flags; defaults are all-False; the runtime stores it on `SandboxRuntime.sharing`. |
| `sandbox_v2/hass_client/tests/test_sandbox_runtime.py::test_runtime_starts_in_locked_down_sharing_posture` | A freshly-spawned runtime with the default config sees `hass.states.async_all() == []` (the locked-down posture's no-subscription contract). |

The websocket dispatcher tests run against the ordinary
`hass_ws_client` fixture handed a scoped access token, so the
end-to-end auth path (token → connection → dispatcher → reject) is
exercised against the real code, not a stub.
