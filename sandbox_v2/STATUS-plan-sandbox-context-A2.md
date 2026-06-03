# STATUS — plan-sandbox-context Phase A2

**One-line:** Deleted `RemoteStore` + `install_remote_store` + the
`restore_state` store-swap workaround; the `current_sandbox` contextvar is
now the sole route for sandbox `Store` IO, with the save branch moved down
to `Store._async_write_data` so delayed/FINAL_WRITE saves reach main. All
suites green, prek clean, single commit.

**Commit:** `4c85363668b` (`sandbox_v2: delete RemoteStore; route writes
via contextvar (Phase A2)`) on branch `sandbox` — **not pushed** (parent
pushes).

## The load-bearing fix: contextvar branch moved to `_async_write_data`

A1 put the save branch in `Store.async_save`. But `async_delay_save` and
the `EVENT_HOMEASSISTANT_FINAL_WRITE` flush **never call `async_save`** —
they funnel `self._data` through `_async_handle_write_data` →
`_async_write_data`. While `RemoteStore` existed it overrode
`_async_write_data`, so those paths reached main anyway. Deleting
`RemoteStore` without this fix would have silently written delayed/final
saves to the sandbox tempdir (data loss).

`homeassistant/helpers/storage.py`:
- **Added** the contextvar branch as the first lines of
  `_async_write_data`: `if sandbox := current_sandbox.get(): await
  sandbox.async_store_save(self.key, data); return`. This covers
  `async_save`, `async_delay_save`, and FINAL_WRITE uniformly (they all
  reach `_async_write_data`).
- **Removed** the `async_save` contextvar branch — single source of truth
  at `_async_write_data`. `async_save` now falls through to
  `_async_handle_write_data` (same as the disk path), which also means the
  sandbox write path now respects `_read_only` and the write-lock —
  matching the old `RemoteStore` (it inherited `_async_handle_write_data`).
- `_async_load_data` and `async_remove` contextvar branches are unchanged
  from A1.
- The bridge owns envelope normalisation (resolving a deferred `data_func`)
  + orjson preserialise + transport, so `_async_write_data` just delegates
  the raw envelope. `_FakeBridge` in the tests was taught the same
  `data_func` resolution to stay a faithful double.

## What got deleted

- `sandbox_v2/hass_client/hass_client/remote_store.py` (the subclass +
  `install_remote_store`/uninstall)
- `sandbox_v2/hass_client/tests/test_remote_store.py`
- In `sandbox_v2/hass_client/hass_client/sandbox.py`:
  - the `from .remote_store import …` import
  - the `install_remote_store(self._channel)` call + the
    `uninstall_remote_store` variable and its teardown
  - the `data.store = RemoteStore(…)` swap in `_load_restore_state` (now a
    vanilla `Store`; the contextvar reaches the import-captured reference)
  - the now-unused `JSONEncoder` import
  - stale `RemoteStore` mentions in `_run_graceful_shutdown` docstrings/
    comments

## New regression test

`sandbox_v2/hass_client/tests/test_sandbox_bridge.py::test_delayed_save_flushes_through_bridge`
— sets `current_sandbox` to the `_FakeBridge`, builds a `Store`, calls
`async_delay_save(lambda: {"foo": "bar"}, delay=0)`, fires
`EVENT_HOMEASSISTANT_FINAL_WRITE` + `async_block_till_done()`, and asserts
`bridge.saved["delayed"]["key"] == "delayed"` and
`bridge.saved["delayed"]["data"] == {"foo": "bar"}`. This is the guard that
fails if the save branch ever regresses back to `async_save`-only.

`test_shutdown.py::test_shutdown_flushes_pending_delay_save` (the existing
Phase 12 delayed-save test) still passes **unchanged in behaviour** — the
FINAL_WRITE flush runs inside the shutdown handler's task, which inherits
the contextvar set in `run()`, so the write reaches the bridge. Only its
stale `RemoteStore`/`install_remote_store` comments were updated.

## Doc updates

- `sandbox_v2/CLAUDE.md` — "Core HA files modified" now says **four**
  files; added the `helpers/sandbox_context.py` + `helpers/storage.py`
  row; updated the Iron-Law note and the repo-layout `RemoteStore` →
  `ChannelSandboxBridge`.
- `sandbox_v2/OVERVIEW.md` — comparison table, ASCII runtime diagram,
  restore-state warm-load paragraph, the whole "Store routing" section, and
  the file map all rewritten around the contextvar.
- `sandbox_v2/docs/FOLLOWUPS.md` — added a "plan-sandbox-context" section
  closing the monkey-patch-the-storage-module tension; de-named the one
  `RemoteStore` mention in the Phase 12 narrative.
- `sandbox_v2/architecture.html` — TOC, runtime diagram box, restore-state
  callout, the §10 "Store routing" section, the timeline card, and the file
  map all stripped of `RemoteStore`/`install_remote_store`.
- `homeassistant/components/sandbox_v2/{protocol.py,__init__.py}` — three
  comment/docstring `RemoteStore` references reworded (these are in
  `homeassistant/`, so they had to go to keep that grep clean).

## Test results

- `uv run pytest sandbox_v2/hass_client/ -q` → **50 passed** (was 55;
  removed `test_remote_store.py`'s 6 tests, added 1).
- `uv run pytest tests/components/sandbox_v2/ tests/helpers/test_storage.py tests/helpers/test_restore_state.py --no-cov -q`
  → **190 passed**.
- `uv run prek --files <11 changed files>` → clean (ruff, ruff-format,
  codespell, prettier, mypy, pylint all Passed). Commit's own pre-commit
  run also passed — no `--no-verify`.

## Verification greps

- `grep -rn "RemoteStore\|install_remote_store" homeassistant/` → **empty.** ✅
- All **live code** under `sandbox_v2/` + the four enumerated docs
  (CLAUDE.md, OVERVIEW.md, FOLLOWUPS.md, architecture.html) → **empty.** ✅

⚠️ **The brief's `grep -rn … sandbox_v2/` "must be empty" is NOT fully
empty** — and cannot be, given the brief's other hard rules. The residual
references are exactly the files the brief told me not to touch:
- **Historical STATUS files** — `STATUS-phase-7/8/9/12.md` and
  `STATUS-plan-sandbox-context-A1.md` (brief: "Don't rewrite historical
  STATUS-phase-*.md files. Leave them alone." The A1 STATUS is likewise a
  historical landing record.)
- **Plan files** — `plans/plan-sandbox-context.md` (brief hard rule #1:
  do not modify the plan file), plus `plan.md`, `plans/plan-ephemeral-sources.md`,
  `plans/whats-changed.md` (other plan docs; left untouched as conservative
  scope — note `whats-changed.md:39` has an unchecked
  "[ ] install_remote_store monkey-patch removed" box that is now true and
  the parent may want to tick).
- **Reference docs** — `README.md`, `generate_backlog.py` (a string about
  main-side key validation), `docs/auth-scoping-decision.md` — all
  describing Phase 8 history.

If the parent wants a literally-empty grep, those are the files to sweep,
but every one is either explicitly protected by the brief or a historical
record where the past-tense `RemoteStore` mention is accurate.

## Things to look at

1. **`architecture.html` is now committed (2744 lines).** It was an
   **untracked** file before this session (never in git history — created
   by an earlier session and left uncommitted; A1's STATUS explicitly
   avoided touching it). The brief's Phase E lists it as a doc to update
   with specific line numbers, so I updated **and committed** it — otherwise
   my edits would live nowhere. If you'd rather it not enter history via
   the A2 commit, that's a `git rm --cached` + separate decision. Flagging
   because it's a large new blob riding in on this commit.
2. **`test_shutdown.py` needed no behavioural change**, only comment
   updates — the contextvar genuinely propagates into the shutdown
   handler's task (set in `run()` before `_channel.start()`, inherited via
   `create_task`). Confirmed green. This also retired Risk #2's worry that
   A1/A2 would have to rewire that test against the rebinding.
3. **No change to `IGNORE_INTEGRATIONS_WITH_ERRORS`** (hard rule #5), the
   plan file, hassfest, or the pre-existing unrelated untracked files
   (`tests/testing_config/.storage/*`, `.claude/scheduled_tasks.lock`).
