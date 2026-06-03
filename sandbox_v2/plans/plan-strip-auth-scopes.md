# Plan: strip `RefreshToken.scopes` from core, keep the sandbox token plain

> **Execute after `plan-sandbox-context.md`.** Phase 7's
> `RefreshToken.scopes` + dispatcher enforcement was built for a sandbox
> websocket-back-to-main that doesn't exist yet. The sandbox still needs a
> credential (system user + access token), but the scoping mechanism in
> **core HA** is dead weight until share-states actually ships. Rip it out;
> reintroduce when a real consumer forces the design.

## Why

- The sandbox **does not open a websocket back to main today.** No code path
  exercises the scope check end-to-end against a real subscription/RPC; the
  feature is asserted only by an isolated dispatcher test.
- Phase 20 already deleted `SharingConfig` / `share_states` /
  `share_entity_registry` / `share_areas` — the *positive opt-in for data*
  that paired with scope-as-deny. With that gone, scopes are guarding a
  non-existent attack surface.
- The mechanism added surface to four core HA files (`auth/models.py`,
  `auth/__init__.py`, `auth/auth_store.py`,
  `components/websocket_api/connection.py`) plus persisted on-disk auth-store
  shape (`scopes` key in the refresh-token dict). That's permanent core
  surface in exchange for zero current value.
- The auth-scoping-decision doc itself flagged two open hardening items
  (`_client_id_for_group` unused; "anyone can set `scopes`" is open trust
  surface; rotation-on-respawn deferred). Better to delete the whole
  primitive and redesign with a concrete consumer in hand than to keep
  patching speculation.
- v1 ran a sandbox subprocess against a plain unrestricted system-user
  token for its entire life. That posture is **not worse than today's v2** —
  no WS path is open in either case. Going back to it removes risk surface;
  reintroducing scoping when the WS lands is a green-field design.

## What stays / what goes

**Stays — the sandbox still needs a credential:**
- Dedicated system user per sandbox group (`"Sandbox v2: built-in"` etc.)
  — same shape as v1; used by the manager to identify the subprocess and by
  the runtime to authenticate when a connection eventually exists.
- Access token freshly minted on each spawn from the system user's refresh
  token — `hass.auth.async_create_access_token(refresh_token)`.
- The CLI `--token` plumbing is unchanged.

**Goes — the entire `scopes` mechanism:**
- `RefreshToken.scopes` field.
- `AuthManager.async_create_refresh_token`'s `scopes=` parameter.
- `AuthStore.async_create_refresh_token`'s `scopes=` parameter + the on-disk
  read/write of the `scopes` key.
- `ActiveConnection.scopes` storage + `_scope_allows` helper + the
  `async_handle` enforcement branch.
- `SANDBOX_TOKEN_SCOPES` constant in `components/sandbox_v2/auth.py` and the
  `scopes=` argument to `async_create_refresh_token`.
- The lookup-by-scope-set in `_get_or_create_sandbox_refresh_token` (it
  used `scopes` to identify the right token among multiple). Replace with
  lookup by `client_id` (use the existing `_client_id_for_group` —
  auth-scoping-decision.md §"Trade-offs" already flagged it as kept-for-this
  case).

## Auth-store backwards compatibility

The on-disk auth store may contain refresh tokens with a `scopes` list (any
HA instance that ran the Phase-7 code at least once). Two options:

- **(A) Silent drop on load.** Auth store's `_async_load` skips the
  `scopes` key when reconstructing `RefreshToken`. The on-disk `scopes`
  list lingers but is unread; next write strips it. Tokens are
  effectively un-scoped (which matches the new behavior — no enforcement).
  **Zero migration code, no storage-version bump.**
- **(B) Rewrite on first load.** Read the store, drop `scopes` from every
  refresh-token dict, write back. Cleaner on-disk shape immediately.

**Recommendation: (A).** v2 isn't released; the only HA instances with
scoped tokens on disk are dev machines running this branch. A silent drop
on load is safe (the field defaulted to `None` already) and avoids touching
the auth store's persistence path. Document the lingering `scopes` key as
a no-op leftover that will eventually disappear on natural token rotation.

## Phases

### Phase A — Strip the core HA surface
**Single PR.** All four core HA files revert in lockstep so no intermediate
state has a half-wired feature.

- `homeassistant/auth/models.py` — delete the `scopes:
  frozenset[str] | None = None` field from `RefreshToken`.
- `homeassistant/auth/__init__.py` — delete `scopes=` parameter from
  `AuthManager.async_create_refresh_token` (and any forwarding).
- `homeassistant/auth/auth_store.py` — delete `scopes=` parameter from
  `AuthStore.async_create_refresh_token`; delete the sort-on-write +
  read-and-frozenset-on-load of the `scopes` key. Add a one-line
  back-compat shim in `_async_load_refresh_token` (or wherever the load
  reconstructs the token) that pops `"scopes"` from the data dict if
  present — silent drop, option (A) above.
- `homeassistant/components/websocket_api/connection.py` — delete
  `self.scopes` storage, the `_scope_allows` helper, and the enforcement
  branch in `async_handle`. `async_handle` reverts to its pre-Phase-7 shape.

**Tests removed:**
- `tests/components/websocket_api/test_scopes.py` — deleted entirely.
- `tests/auth/test_init.py` — the scoped-token round-trip test (and the
  "pre-existing tokens without scopes load as None" test) deleted.

### Phase B — Simplify the sandbox-side auth helper
- `homeassistant/components/sandbox_v2/auth.py`:
  - Delete `SANDBOX_TOKEN_SCOPES`.
  - `_get_or_create_sandbox_refresh_token` switches from "match by scope
    set" to "match by `client_id == _client_id_for_group(group)`". This
    means the refresh-token creation call gains `client_id=...` — but
    system-user refresh tokens are `TOKEN_TYPE_SYSTEM` which don't carry a
    `client_id` today (see the existing docstring). Two options:
    1. Switch the sandbox token from `TOKEN_TYPE_SYSTEM` to
       `TOKEN_TYPE_NORMAL` so `client_id` is honoured. Aligns with v1's
       behaviour. Mild change in token shape; verify no other code branches
       on the system-user token type.
    2. Identify the token by matching the system user's name +
       `len(user.refresh_tokens) == 1` (one token per system user). Simpler;
       relies on the invariant that we only ever create one refresh token
       per sandbox user.
  - **Recommendation: option 2.** System-user tokens are the natural
    shape for "internal credential, not user-facing"; v1 used them. The
    "one token per system user" invariant is easy to assert in the helper
    itself.
- `tests/components/sandbox_v2/test_auth.py` — update assertions: the
  helper still creates exactly one system user per group and one refresh
  token, but no scope-set check.

### Phase C — Docs
- `sandbox_v2/docs/auth-scoping-decision.md` — prepend a "SUPERSEDED
  2026-06-03" header noting the mechanism was reverted because no consumer
  shipped; keep the doc as historical record of the design + trade-offs so
  the next attempt has the prior thinking.
- `sandbox_v2/CLAUDE.md` "Core HA files modified" — delete the
  `auth/models.py + auth/__init__.py + auth/auth_store.py +
  components/websocket_api/connection.py` row entirely. v2's core HA
  touch list shrinks from four files to two (plus the contextvar one
  added by `plan-sandbox-context.md` — net: three).
- `sandbox_v2/OVERVIEW.md` "Scoped auth" section — rewrite as "Sandbox
  auth: plain system-user token; scope enforcement deferred to whenever
  the sandbox→main connection lands."
- `sandbox_v2/docs/FOLLOWUPS.md` — open a follow-up item: "Re-introduce
  scope enforcement when the WS transport (`plan-transport.md` T4) ships
  share-states subscription. Reuse `auth-scoping-decision.md`'s design as
  the starting point."
- `sandbox_v2/architecture.html` — strip any "scoped token" / "scope
  enforcement" language.

## Touch points

```
homeassistant/auth/models.py                              (delete scopes field)
homeassistant/auth/__init__.py                            (delete scopes kwarg)
homeassistant/auth/auth_store.py                          (delete scopes serialization; add load-time pop)
homeassistant/components/websocket_api/connection.py     (delete _scope_allows + enforcement)
homeassistant/components/sandbox_v2/auth.py              (simplify; lookup by user, not scope set)
tests/components/websocket_api/test_scopes.py            (DELETE)
tests/auth/test_init.py                                   (delete scoped-token cases)
tests/components/sandbox_v2/test_auth.py                  (update assertions)
sandbox_v2/docs/auth-scoping-decision.md                  (prepend SUPERSEDED header)
sandbox_v2/CLAUDE.md                                       (shrink core-HA-modified list)
sandbox_v2/OVERVIEW.md                                     (rewrite scoped-auth section)
sandbox_v2/docs/FOLLOWUPS.md                               (add re-introduce follow-up)
sandbox_v2/architecture.html                              (strip scope language)
```

## Sequencing

- **Executes after `plan-sandbox-context.md`.** No technical coupling, but
  the auth revert is the *second* surface-shrinking move in the batch and
  the user wants the contextvar primitive locked in first.
- **Executes before everything else in the batch** — fidelity, transport,
  ephemeral-sources, docker. Each of those touches surface that today
  carries the scope-aware code paths; cleaning house first keeps each
  later PR focused.
- **Hard dependency: none.** The revert is mechanical; the only ordering
  call is "contextvar first" per user preference.

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **A refresh token persisted with `scopes` causes a load error after the field is removed.** The serialized dict will have a `scopes` key the dataclass no longer accepts. | Medium (dev instances on this branch) | Medium (auth store load failure) | The load-time `pop("scopes", None)` shim (option A above) — one line in `_async_load_refresh_token`. Add a regression test: hand-craft an on-disk auth store dict with `scopes` in a refresh token, assert load returns a normal `RefreshToken` with no leftover attribute. |
| 2 | **Out-of-tree code uses `RefreshToken.scopes` or `AuthManager.async_create_refresh_token(scopes=...)`.** The feature shipped on a branch only; in practice the surface is internal. | Trivial | Trivial | None needed. Grep `homeassistant/` + `tests/` for `scopes` references and confirm only sandbox-Phase-7 code uses them before deleting. |
| 3 | **A future security review wants the dispatcher enforcement reinstated quickly.** Worth being able to revert this revert cleanly. | Low | Low | The PR's commit history is the rollback. `auth-scoping-decision.md` stays as the design record for re-introduction. |

## Verification checklist

- [ ] `grep -rn "scopes" homeassistant/auth/ homeassistant/components/websocket_api/` returns only string-literal noise (URL paths, etc.), no field/parameter references.
- [ ] `grep -rn "SANDBOX_TOKEN_SCOPES\|_scope_allows" .` returns empty.
- [ ] `grep -rn "scopes=" homeassistant/ tests/` returns no calls.
- [ ] An auth store with a pre-existing scoped refresh token loads without warning or error (test).
- [ ] `uv run pytest tests/components/sandbox_v2/ --no-cov -q`,
      `uv run pytest tests/auth/ --no-cov -q`,
      `uv run pytest tests/components/websocket_api/ --no-cov -q` all green.
- [ ] `uv run prek run --files <changed>` clean.

## Final phase — docs up to date

Already covered in Phase C above. After this plan lands, the standing CLAUDE.md
list of "core HA files modified" reads:
- `homeassistant/config_entries.py` (router + `ConfigEntry.sandbox`)
- `homeassistant/helpers/entity_component.py`
  (`async_register_remote_platform`)
- `homeassistant/helpers/sandbox_context.py` (new, from `plan-sandbox-context`)
- `homeassistant/helpers/storage.py` (`Store` reads contextvar, from
  `plan-sandbox-context`)

The auth/* row is gone.
