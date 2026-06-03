# STATUS — plan-sandbox-context Phase A1

**One-line:** `current_sandbox` ContextVar landed in core HA; `Store`
load/save/remove route to a `SandboxBridge` when set; the sandbox runtime
sets it before warm-load. Additive only — `install_remote_store` stays, both
paths active. All suites green, prek clean, single commit.

**Commit:** `d0bbd340289b566c2f4ca26b879a1bf2f71f413f`
(`sandbox_v2: route Store IO via current_sandbox contextvar (Phase A1)`)
on branch `sandbox` (not pushed — parent pushes).

## What landed

| File | Change |
|------|--------|
| `homeassistant/helpers/sandbox_context.py` | **NEW.** `current_sandbox: ContextVar[SandboxBridge \| None]` (`default=None`) + `SandboxBridge` Protocol (3 store methods only; IR/RF deferred per Q1). Module + Protocol docstrings carry the Risk #3 "never set from main-side code" rule. Matches `helpers/http.py` / `helpers/chat_session.py` shape. |
| `homeassistant/helpers/storage.py` | Import `current_sandbox`. `_async_load_data`: new `elif sandbox := current_sandbox.get():` branch fetches the wrapped envelope via `async_store_load` (returns `None` → `None`); the existing migration block runs unchanged against it (design **B**). `async_save`: contextvar branch is the first action after building the wrapped dict — pushes via `async_store_save`, clears `_data`, returns (bypasses write-lock/manager/final-write machinery). `async_remove`: keeps the in-memory invalidate + listener cleanup (matching `RemoteStore.async_remove`), then branches to `async_store_remove`. |
| `sandbox_v2/hass_client/hass_client/sandbox_bridge.py` | **NEW.** `ChannelSandboxBridge` — three store methods over `MSG_STORE_LOAD/SAVE/REMOVE`, bodies lifted from `RemoteStore` incl. the orjson preserialise (`prepare_save_json` → `json.loads`) on save and the same `ChannelClosedError`/`ChannelRemoteError` handling. |
| `sandbox_v2/hass_client/hass_client/sandbox.py` | Import `current_sandbox` + `ChannelSandboxBridge`. In `run()`, inside `if self._channel is not None:` and **before** `install_remote_store` / `start` / `_load_restore_state` / handler registration: `assert current_sandbox.get() is None` (Risk #3), then `sandbox_token = current_sandbox.set(ChannelSandboxBridge(self._channel))`. `install_remote_store` **kept** (both paths active). Teardown `finally` does `current_sandbox.reset(sandbox_token)`. Added a comment documenting the registry-ordering caveat from the plan's touch-points audit. |
| `sandbox_v2/hass_client/tests/test_sandbox_bridge.py` | **NEW.** The five required tests + one extra (see below). |

## Tests

All commands run from the repo (core env unless noted):

- `uv run pytest sandbox_v2/hass_client/ -q` → **55 passed** (client env;
  includes the new file plus the still-present `test_remote_store.py` and
  `test_shutdown.py`, both green with dual paths active).
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → **138 passed**.
- `uv run pytest tests/helpers/test_storage.py tests/helpers/test_restore_state.py --no-cov -q` → **52 passed** (regression guard for the core `Store` change).
- `uv run prek run --files <the 5 touched files>` → **clean** (ruff, ruff-format, codespell, mypy, pylint, prettier all Passed). Commit's own pre-commit run also passed — no `--no-verify`.

### The six tests in the new file

1. `test_load_routes_to_bridge_and_unwraps` — load via contextvar reaches the `_FakeBridge` by key, returns unwrapped data. (plan #1)
2. `test_load_returns_none_when_bridge_has_no_data` — missing key → `None`.
3. `test_migration_runs_through_bridge` — **parametrized 2-arg / 3-arg** `_async_migrate_func`; migration fires through the contextvar path and the post-migration `async_save` recurses back through the bridge. (plan #2)
4. `test_no_sandbox_round_trip_uses_local_disk` — contextvar unset → real disk save/load round-trip; no-sandbox regression guard. (plan #3)
5. `test_restore_state_warm_load_without_workaround` — vanilla `RestoreStateData` (captured original `Store` at import) routes `async_load` to the bridge purely because the contextvar is set, no store swap. The smoking gun for A2's workaround deletion. (plan #4)
6. `test_contextvar_inherits_across_create_task` — contextvar set in body, task spawned after, load reaches the bridge. (plan #5)

Plus `test_channel_bridge_maps_store_rpcs` — **one extra beyond the required
five** (see Deviations).

## Deviations from the plan

1. **Added a 6th test** (`test_channel_bridge_maps_store_rpcs`) driving the
   real `ChannelSandboxBridge` over an in-memory channel pair. The five
   required tests all use `_FakeBridge` (per plan #1 "no channel"), so none
   of them touch the new `sandbox_bridge.py` file's wire mapping directly —
   it's only covered transitively by the still-present `test_remote_store.py`.
   I judged direct coverage of the new file worth one small test. When A2
   deletes `test_remote_store.py`, this test should stay.

2. **Left `test_shutdown.py` and `test_remote_store.py` unmodified.** Risk #2
   anticipated A1 having to touch `test_shutdown.py`. It didn't need to: with
   both paths active, the `Store` those tests build is still `RemoteStore`
   (install stays), the contextvar branch routes to the bridge over the same
   channel, and both files pass unchanged. Their cleanup is an A2 concern.

## ⚠️ Open issue for the parent to look at BEFORE A2

**`async_delay_save` does NOT route through the contextvar in A1, and the
plan's §2 claim that it does is inaccurate.** Plan §2 says: *"delay_save /
final_write: unchanged … They eventually call `async_save`, which hits the
contextvar branch."* That is **false** for the current `storage.py`:
`async_delay_save` sets `self._data` directly and schedules
`_async_handle_write_data` → `_async_write_data` — it never calls
`async_save`. So my A1 contextvar branch in `async_save` is bypassed by the
delayed-save and FINAL_WRITE-flush paths.

- **A1 impact: none.** `RemoteStore` is still installed and overrides
  `_async_write_data`, so delayed/final-write saves still reach main.
  `test_shutdown.test_shutdown_flushes_pending_delay_save` confirms this
  (green).
- **A2 impact: real.** When A2 deletes `RemoteStore`, delayed saves and the
  FINAL_WRITE flush will fall through to local-disk `_write_prepared_data`
  inside the sandbox tempdir — silent data loss for any `Store` using
  `async_delay_save` (e.g. the restore-state dump path and many integration
  stores). **A2 must add a contextvar branch in `_async_write_data` (or
  `_async_handle_write_data`) — not just `async_save` — before removing
  `RemoteStore`.** Branching at `_async_write_data` mirrors what `RemoteStore`
  did (it overrode exactly that method) and would cover async_save,
  async_delay_save, and final-write uniformly. Recommend A2 either move the
  save branch down to `_async_write_data`, or add a second branch there.

  I did **not** make that change in A1 because the brief/plan explicitly
  scoped A1 to "`async_save` and `async_remove` early-return through the
  bridge," and changing `_async_write_data` is a deviation I'm surfacing
  rather than silently making. The A1 tests don't exercise delayed-save
  through the contextvar, so A1 is internally consistent; the gap is purely
  a forward-looking A2 correctness requirement.

## Notes / smaller things

- **Q3 assertion never fires negatively in the suite.** No test sets
  `current_sandbox` and then re-enters `run()`. The runtime tests
  (`test_shutdown.py`) pass because the teardown `reset(token)` clears it
  between runs. The assertion is purely the two-runtimes-one-loop guard.
- **Risk #5's suggested executor-not-entered test** is not in the required
  five and I didn't add it. It's implicitly satisfied — the load/save
  contextvar branches return before any `async_add_executor_job` call, and
  `_FakeBridge` has no executor interaction — but a dedicated assertion could
  be added in A2 if desired.
- **Registry-ordering caveat** from the plan's touch-points audit is captured
  as a comment next to `current_sandbox.set` in `sandbox.py`.
- Did **not** touch `IGNORE_INTEGRATIONS_WITH_ERRORS` in hassfest (hard
  rule #5), the plan file, or any of the unrelated pre-existing
  modified/untracked files in the worktree (plan docs, `architecture.html`,
  `tests/testing_config/.storage/*`, `.claude/scheduled_tasks.lock`).
