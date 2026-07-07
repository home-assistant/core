Status: DONE

Phase 7 adds the scoped-auth primitive to `RefreshToken`, enforces it
per-command in the websocket dispatcher, and wires sandbox-scoped
access tokens into the manager so each subprocess receives a real
credential instead of the placeholder string. The scope set granted to
sandbox tokens is `{"sandbox_v2/", "auth/current_user"}` — a prefix
grant for the entire `sandbox_v2/` namespace plus a single exact-match
entry that lets the runtime confirm which user it authenticated as.
Opt-in core-data sharing lands as `SandboxGroupConfig` with three
flags (`share_states`, `share_entity_registry`, `share_areas`); the
default posture is everything-off (locked down), and
`DEFAULT_GROUP_CONFIGS` flips all three on for the `built-in` and
`main` groups, matching the behaviour today's built-in integrations
expect. `custom` stays locked down. The runtime accepts the matching
`--share-*` CLI flags into a frozen `SharingConfig` dataclass so a
future phase can hang the actual subscription code off it without
churning the manager↔runtime contract.

The sandbox does not yet open a websocket back to main — the stdio
control channel built in Phases 3-4 is still the only path between
manager and runtime. The scope-enforcement test therefore exercises
the dispatcher directly by handing a scoped access token to the
ordinary `hass_ws_client` fixture. The "share_states=False isolation"
contract is enforced trivially today (no subscription code exists) and
asserted by a hass_client test that confirms a freshly-spawned runtime
sees an empty `hass.states.async_all()`.

Files added:
- `homeassistant/components/sandbox_v2/auth.py`
- `tests/components/sandbox_v2/test_auth.py`
- `tests/components/websocket_api/test_scopes.py`
- `sandbox_v2/hass_client/tests/test_sharing_config.py`

Files changed:
- `homeassistant/components/sandbox_v2/__init__.py` — pass an
  `async_issue_sandbox_access_token`-backed `token_factory` to the
  manager so subprocesses receive a real scoped token.
- `homeassistant/components/sandbox_v2/manager.py` — add
  `SandboxGroupConfig`, `DEFAULT_GROUP_CONFIGS`, `TokenFactory`, the
  `group_config()` accessor, the token-factory plumbing through
  `ensure_started`, and the `--share-*` flag expansion in
  `_default_command`.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — add
  `SharingConfig` dataclass + a `sharing` constructor argument on
  `SandboxRuntime`.
- `sandbox_v2/hass_client/hass_client/sandbox_v2/__main__.py` — add
  `--share-states` / `--share-entity-registry` / `--share-areas`
  flags and feed them into a `SharingConfig` at runtime construction.
- `sandbox_v2/hass_client/tests/test_sandbox_runtime.py` — add the
  locked-down-sharing posture test.
- `tests/components/sandbox_v2/test_manager.py` — add four new tests
  (default + override `group_config`, default-command argv, token
  factory invocation).
- `tests/auth/test_init.py` — add scoped refresh-token defaults +
  round-trip-through-store tests.
- `sandbox_v2/plan.md` — Phase 7 section marked complete with summary
  and inline notes for the deferred "when True, sandbox subscribes"
  half (needs the websocket connection).

Core HA files modified (review surface):
- `homeassistant/auth/models.py:126-134` — `RefreshToken` grows an
  optional `scopes: frozenset[str] | None = None` attr. Default
  `None` preserves today's behaviour for every existing token.
- `homeassistant/auth/__init__.py:453-518` — `AuthManager
  .async_create_refresh_token` accepts and forwards `scopes` to the
  store. Other call sites unchanged.
- `homeassistant/auth/auth_store.py:204-235, 478-500, 561-587` —
  `AuthStore.async_create_refresh_token` accepts `scopes`; the
  persisted dict carries `scopes` as a sorted list; reload uses
  `dict.get("scopes")` so pre-existing stored tokens load with
  `scopes=None`. No storage-version bump needed because the new key
  is optional on read.
- `homeassistant/components/websocket_api/connection.py:43-62,
  79-90, 232-245` — `ActiveConnection` stores `scopes` from the
  refresh token; `async_handle` checks each incoming type via the
  module-level `_scope_allows` helper and rejects with
  `ERR_UNAUTHORIZED`. Unscoped tokens (`scopes is None`) are
  unaffected.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **67 passed** (56 from Phases 0-6 + 5 new test_auth + 4 new
  test_manager + 2 unchanged).
- `cd sandbox_v2/hass_client && uv run pytest -q` → **30 passed**
  (22 from Phases 0-6 + 7 new test_sharing_config + 1 new
  test_sandbox_runtime).
- `uv run pytest tests/auth/ tests/components/websocket_api/
  --no-cov -q` → **336 passed, 2 snapshots passed** — the new
  scopes attribute is backwards-compatible (None default) and the
  new dispatcher check is a no-op for scopes=None tokens.
- `uv run prek run --files <15 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **The sandbox→main websocket is not yet wired.** The manager
  hands the runtime a real scoped access token plus the
  `share_*` flags, and the runtime stores both on
  `SandboxRuntime.sharing`, but nothing actually opens a websocket
  back to main today. Phase 8's `RemoteStore` is the first piece
  that needs it — when that lands, opening the connection and
  subscribing (gated on `sharing.share_states`) is a straight
  extension of the runtime's `run()` setup.
- **`share_states=True` filtering on main is deferred.** The plan
  called for "main's `subscribe_events` and state reads filter to
  data the sandbox is allowed to see" when sharing is on. The
  config knob is in place but the filtering side hasn't shipped —
  it should land in the same PR that turns on the subscription.
  The natural place to gate this is `_scope_allows` plus a
  per-event scope check on the subscription's emit path.
- **Token rotation on sandbox restart.** `_get_or_create_sandbox_refresh_token`
  reuses the same scoped refresh token across calls, so an HA restart
  hands the subprocess the same token it had before. That's fine for
  the locked-down posture but the plan's "rotate the refresh token on
  each call" note in the docstring is currently aspirational — once
  the websocket subscription lands, decide whether to keep the stable
  token (simpler) or rotate (tighter security if a subprocess is
  compromised).
- **No supervisor for hash collisions.** Two HA processes (e.g., dev
  and prod) sharing the same auth store would each create their own
  `Sandbox v2: built-in` user with the same name. That's the same
  shape as the existing supervisor user collision pattern — not new
  in v2 — but worth noting if multi-instance auth stores ever land.
- **`SandboxGroupConfig` is not user-facing.** Per the plan this is
  intentional for v2; surfacing the knob in the frontend is Phase 11+
  follow-up. If a user wants to lock down `built-in` they need to
  override `group_configs=` in code today.
- **Scope-set serialisation is JSON-sorted.** The auth store writes
  `sorted(refresh_token.scopes)` so the on-disk shape is stable
  across reloads; load reconstructs a `frozenset`. The dispatcher
  comparison is set-based, so order does not leak into behaviour.
- **The `_client_id_for_group` helper in `sandbox_v2/auth.py` is
  not used today** — kept for the case where a sandbox refresh token
  needs a stable `client_id` (e.g., to dedupe across HA versions).
  Wire it in if/when the rotation-on-each-call story changes.
