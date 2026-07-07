# STATUS — plan-auth-context (drop token + system user + context restore)

**Done.** Parts A/B/C all landed; both suites green, hassfest clean, prek
clean. The sandbox carries no credential and provably cannot fabricate
`Context` attribution.

## Commits

| SHA | What |
|---|---|
| `6206489b5fd` | Parts A/B/C — code + tests (token gone, system user gone, context restoration) |
| `83cc4d4a07c` | Docs (ARCHITECTURE §8/§10 + changelog, OVERVIEW, FOLLOWUPS, auth-scoping-decision, CLAUDE) |

Two commits (code, then docs) — each leaves the tree green. Not pushed
(parent pushes). No `--no-verify`; pre-commit passed on both.

## Part A — token dropped end-to-end

- `manager.py`: `_default_command` no longer emits `--token`; dropped the
  `TokenFactory` type, the `token_factory` ctor param, `self._tokens`, and
  the token-fetch block in `ensure_started`.
- `__init__.py`: removed the `async_issue_sandbox_access_token` import, the
  `_issue_token` callback, and `token_factory=` from the `SandboxManager`
  construction.
- Runtime `hass_client/sandbox/__init__.py`: dropped `SandboxRuntime.token`
  (field + ctor param) and the docstring mention. **Note:** the
  `sandbox_token` local in `run()` is the `current_sandbox` contextvar
  *reset* token — unrelated, left intact.
- `hass_client/sandbox/__main__.py`: removed the `--token` argument + its
  plumbing into `SandboxRuntime`.
- Docker: `SANDBOX_TOKEN` removed from `docker-entrypoint.sh`,
  `docker-compose.test.yml`, and the env-var table in `docs/docker.md`.

## Part C — per-group system user dropped

- `auth.py` **deleted entirely** — both `async_issue_sandbox_access_token`
  (Part A) and `async_get_or_create_sandbox_user` (Part C) are gone, so
  nothing remained. Imports removed from `bridge.py` and `__init__.py`.
- `bridge.py`: removed `_async_system_user_id` and `self._system_user_id`.
- A genuinely sandbox-originated context is now `Context(user_id=None)`.
- **Future-work note left, not built:** a `Context` group attribute (which
  sandbox group originated an action) — captured in FOLLOWUPS.md "Still
  open" + ARCHITECTURE §10/§13. Needs a core `Context` field change.

## Part B — context-id restoration

**Where the cache is seeded (the real gap the design wanted closed).** The
T2 cache was only seeded by sandbox-*inbound* resolution; it was never
seeded where main hands a real `Context` *down*. Seeded at both call-down
sites:

1. **Service forwarder** (`_build_service_forwarder._forward`, ~line 790):
   `bridge._remember_context(call.context)` right before sending
   `request.context_id = call.context.id`.
2. **Entity-call path.** `SandboxProxyEntity._call_service` now passes
   `context=self._context` (the Context the service framework sets on the
   entity for the in-flight call — `service.py` calls
   `entity.async_set_context(call.context)` before invoking the method).
   `SandboxBridge.async_call_service` took a new `context: Context | None`
   param: it calls `self._remember_context(context)` and then reduces to
   `context_id = context.id` for the batcher. **The full Context is threaded
   only as far as `async_call_service` (the single caller is the proxy);
   the `_CallServiceBatcher` still carries just `context_id`** — so no
   invasive batcher refactor, and every Context main sends down is
   remembered regardless of how calls coalesce.

**Event-down path:** there is none. Events only flow sandbox→main
(`_handle_fire_event`); main never forwards an event into a sandbox, so
there was nothing to seed there. Confirmed by grep.

**Refinement honored (the mid-task correction):**
- **Bounded by a 15-minute TTL, not a size cap.** `_CONTEXT_TTL =
  timedelta(minutes=15)`. The cache is an `OrderedDict` kept in
  insertion/expiry order (every write `move_to_end`s its key); since the
  TTL is constant, insertion order *is* expiry order, so `_prune_contexts`
  is a cheap front-to-back walk that stops at the first live entry, run
  lazily on every `_remember_context` / `_resolve_context`. A
  `_CONTEXT_CACHE_MAX = 2048` count cap remains only as a sanity backstop.
- **Unknown id → main's OWN id, never the sandbox ULID.** `_resolve_context`
  for an unknown/expired id mints `Context(user_id=None)` (fresh
  main-generated id) and caches it **under the sandbox-supplied string as a
  key only** — the sandbox's id is never adopted as the Context's identity,
  because `context_id`s are ULIDs with an embedded ms timestamp main can't
  trust (a crafted id could back-/forward-date an event; recorder/logbook
  order by it).

`_resolve_context` / `_remember_context` are now sync (`@callback`) — the
system-user lookup was the only `await`, and it's gone; the two
`_handle_*` call sites dropped their `await`.

## Tests

- **HA-side:** `uv run pytest tests/components/sandbox/ --no-cov -q` →
  **197 passed**. (The protobuf `Struct` map-ordering test
  `test_protobuf_codec_round_trip_is_byte_identical` is pre-existing flaky —
  seed/order-dependent map serialization, not in this diff; it passed on
  every run except one randomly-ordered full-suite pass, and passes
  deterministically with `-p no:randomly`.)
- **Client-side:** `uv run pytest sandbox/hass_client/ -q` → **77 passed**.
- **hassfest:** `python -m script.hassfest --action validate` → 0 invalid
  integrations (the `turbojpeg` RuntimeError line is an unrelated import
  warning from another integration, not a validation failure).
- **prek:** clean on all touched files (one ruff RUF059 auto-fixed: an
  unused `bridge` → `_bridge` in the new test; one import re-sort).

New / changed tests:
- `test_bridge.py::test_forwarded_context_restores_on_echoed_state` —
  end-to-end known-id restore: a `ServiceCall` with
  `Context(user_id="user-1", parent_id="parent-1")` is forwarded into the
  sandbox; the sandbox echoes that `context_id` on a `state_changed`; the
  applied proxy state carries the **original** Context (verbatim).
- `test_proto_transport.py`:
  - `test_resolve_context_restores_known_and_mints_fresh_unknown` — known
    restores verbatim; unknown gets `user_id=None` with `id != sandbox_id`
    (stable on repeat); `None` → `user_id=None`.
  - `test_resolve_context_entry_expires_after_ttl` — `freezer.tick(TTL+1s)`;
    the evicted id degrades to a fresh `user_id=None` context, no error.
  - `test_wire_messages_carry_only_context_id_no_attribution` — no-forgery:
    `StateChanged` / `FireEvent` / `CallService` descriptors have
    `context_id` but no `parent_id` / `user_id` field.
  - `test_state_changed_unknown_context_gets_fresh_no_user` — rewrite of the
    old system-user test: an unknown `context_id` lands with `user_id=None`,
    `parent_id=None`, and `id != "sandbox-ctx-1"`.
- `test_auth.py` **deleted** (both helpers it tested are gone).
- `test_manager.py::test_default_command_carries_name_and_url_only` —
  asserts `--token` not in argv (replaced the two token-factory tests).
- Spawn-factory tests that drove the real runtime
  (`test_phase4_subprocess`, `test_phase9_shutdown`, `test_transport_unix`)
  had their `--token …` argv pairs removed — otherwise the now-stricter
  argparser would `SystemExit` and the subprocess would fail to start.
- Client tests (`test_sandbox_runtime`, `test_transport_scheme`,
  `test_shutdown`, `pytest_plugin`) dropped `token=` / `--token`;
  `test_cli_parser_accepts_name_and_url` now also asserts `--token` is
  rejected. (The `current_sandbox.set/reset` tokens in
  `test_sandbox_bridge.py` are the contextvar reset token — left intact.)

No assertions were silently loosened — the rewrites flip the *expected
value* to match the new model (user_id None / id-not-adopted) and add
stronger checks (id ≠ sandbox id, no-forgery field check).

## Greps (hold)

- `grep -rn --include=*.py "async_get_or_create_sandbox_user|_system_user_id|async_issue_sandbox_access_token" homeassistant/ sandbox/` → **empty** (only matches are in historical STATUS-*/plan-* docs and the FOLLOWUPS narrative describing the removal).
- `grep -rn "\-\-token|SANDBOX_TOKEN|\.token\b" homeassistant/components/sandbox/ sandbox/hass_client/hass_client/sandbox/` → **empty** (no live token plumbing).

## Docs updated

ARCHITECTURE.md (§2 table, §5 spawn cmd, §8 context model, §10 auth
rewrite, §13 future-work, changelog row), OVERVIEW.md (auth row, spawn
blocks, EventMirror context paragraph, auth section + new Context-restoration
subsection, file-pointer table), docs/FOLLOWUPS.md (narrative entry + two
refreshed "Still open" items), docs/auth-scoping-decision.md (one-line
further-superseded note), CLAUDE.md (auth-scoping-decision pointer).

## Anything weird

- The plan file's Part B touch-point still mentions `event_mirror?` and
  "folds the T2 `_resolve_context`" — there is no separate event_mirror
  module on the main side (re-fire lives in `bridge._handle_fire_event`),
  and `_resolve_context` already existed (T2); Part B seeded it at the
  call-down sites and changed the unknown-id branch. No blocker.
- Did **not** modify the plan file, the historical STATUS-* files, the
  WebSocket transport, or reintroduce any scope mechanism. Did **not**
  build the future `Context` group attribute (note left only).
