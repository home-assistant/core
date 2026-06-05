Status: DONE

Phase 15 closes the deferred Phase 10b sweep: it lands the
`MockConfigEntry.add_to_hass` autotag patch, fixes two `run_compat.py`
plumbing gaps that prevented the runner from ever finding a real
test, and produces the first real `COMPAT.md` / `COMPAT.csv` numbers
against v1's 37-integration baseline. **No core HA files touched** —
Phase 15 is entirely test infrastructure + runner plumbing +
documentation.

Headline: 29 of 37 integrations fully pass; 7,586 of 7,648 tests
pass (99.19%). Every one of the 62 failures buckets into a single
`test-only` root cause — the autotag patch mutates `entry.data` to
add `__sandbox_group: built-in`, and a handful of helper integration
tests (`group`, `template`, `min_max`, `derivative`, `threshold`,
`utility_meter`, `integration`, `proximity`) inspect that data dict
directly (assertions like `entry.data == {}`, or Syrupy snapshots).
Confirmed by re-running the same files **without** the sandbox
plugin: 107/107 pass, so every failure traces back to the patch
making the routing tag observable. The bridge code paths exercised
by the suite (router setup, all 32 entity proxies, service mirror,
event mirror, restore_state warm-load, schema bridge) pass cleanly
on every integration.

The autotag patch lives in
`sandbox_v2/hass_client/hass_client/testing/_autotag.py`. It
re-implements the Phase 2 classifier synchronously (manifest +
`os.listdir` walk; same five-rule order — `ALWAYS_MAIN` check,
manifest `integration_type == "system"` check, deny-listed platform
check, custom vs built-in fallback) because the real classifier
takes an async-loaded `Integration` and would require driving a
coroutine from inside the running event loop the test is already on.
Both compat plugins install it in `pytest_configure` and tear it
down in `pytest_unconfigure`. The patch wraps
`MockConfigEntry.add_to_hass`: when the entry's domain classifies to
a sandbox group and `entry.data` doesn't already carry
`__sandbox_group`, it builds a new `MappingProxyType` with the tag
injected and uses `object.__setattr__` to overwrite `entry.data`
(mirroring the trick `ConfigEntry.__init__` uses to freeze the
field), then delegates to the original `add_to_hass`. Idempotent and
reversible.

Two `run_compat.py` fixes were needed for the runner to find tests
at all:

1. `cwd` was `sandbox_v2/hass_client/`, but `tests/conftest.py`
   imports freezegun / pytest-aiohttp / other HA test deps that are
   only installed in the core uv env. Changed to `CORE_ROOT`
   (`sandbox_v2/..`). The hass_client env's own tests still run from
   that env via `cd sandbox_v2/hass_client && uv run pytest`.
2. The pytest invocation now passes `--no-cov` so per-integration
   runs don't fail the pytest-cov plugin hook (it requires every
   test path resolve against the configured `cov` source).

`run_compat.py` also got a third change: its markdown default-output
path moved from `COMPAT.md` to `COMPAT_LATEST.md` so the curated
Phase 15 baseline report at `COMPAT.md` isn't silently overwritten by
ad-hoc runs. `COMPAT.csv` is still the canonical machine-readable
artifact.

Files added:
- sandbox_v2/hass_client/hass_client/testing/_autotag.py
- sandbox_v2/hass_client/tests/test_autotag.py
- sandbox_v2/STATUS-phase-15.md (this file)

Files changed:
- sandbox_v2/hass_client/hass_client/testing/pytest_plugin.py —
  install autotag in `pytest_configure` and tear down in
  `pytest_unconfigure`.
- sandbox_v2/hass_client/hass_client/testing/conftest_sandbox.py —
  same autotag install/teardown alongside the existing freezer
  marker registration.
- sandbox_v2/run_compat.py — `cwd=CORE_ROOT` so core test conftest
  imports resolve; pass `--no-cov`; default markdown output moved to
  `COMPAT_LATEST.md` to preserve curated `COMPAT.md`.
- sandbox_v2/COMPAT.md — curated Phase 15 baseline report with
  bucketed triage table, v2-vs-v1 comparison, and the single
  follow-up that closes the v1-removal gap.
- sandbox_v2/COMPAT.csv — fresh 37-integration baseline numbers.
- tests/components/sandbox_v2/test_testing_plugins.py — add
  end-to-end autotag test (`test_autotag_mutates_mock_config_entry_data`);
  wrap `test_conftest_sandbox_registers_marker_in_configure` in
  try/finally so the autotag side-effect of `pytest_configure` is
  torn down via `pytest_unconfigure` instead of leaking into the
  rest of the suite.
- sandbox_v2/plan.md — Phase 15 marked complete with the
  per-checkbox summary.

Core HA files modified (review surface):
- None. (Phase 15 is plugin-side, runner-side, and documentation only.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **134 passed** (133 from Phase 0–14 + 1 new
  `test_autotag_mutates_mock_config_entry_data`).
- `cd sandbox_v2/hass_client && uv run pytest -q` →
  **51 passed** (46 from Phase 0–14 + 5 new `test_autotag.py` cases).
- `.venv/bin/prek run --files <7 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, prettier, pylint).
- `cd sandbox_v2 && uv run python run_compat.py <37 v1 integrations>`
  → 29 pass, 8 issues, 7,586 tests passed, 62 failed, 17 skipped
  (99.19% test-level pass rate).

Things to flag for the next phase:

- **The 99.19% rate is below the 99.5% v1-removal threshold.** The
  single follow-up that closes the gap is "move the sandbox-group
  tag off `entry.data`". Two viable shapes: (a) carry the group on a
  side-channel mapping
  (`hass.data[DATA_SANDBOX_V2].group_for_entry[entry.entry_id]`)
  instead of mutating `entry.data`; or (b) keep `entry.data` clean
  and re-derive the group on every router lookup via the classifier
  when no explicit tag is present. Either approach removes the
  observable footprint and the 62 test-only failures vanish. v1
  removal stays deferred (per Phase 11) until that follow-up lands.
- **The sync classifier duplicates ~30 LOC of the real classifier.**
  Justified — the real one needs an async-loaded `Integration` and
  the compat tests are already inside the event loop — but it can
  drift. The Phase-2 classifier tests catch behavioural drift on the
  real side; the new `tests/test_autotag.py` pins the sync side. If
  the deny-list grows, both lists need updating.
- **`run_compat.py` runs strictly serially.** The 37-integration
  Phase 15 sweep took ~3 min wall time; the full
  `homeassistant/components/` tree (Phase 16's scope) is hundreds of
  integrations and will need pytest-xdist (`-n auto`) to finish in
  hours instead of half a day. Flagged in the Phase 16 spec already.
- **`run_compat.py` still depends on `uv run python -m pytest`
  resolving in the core env.** Documented in COMPAT.md's
  "Reproducing this report" section, but the runner doesn't sanity-
  check that the core venv is present before spawning subprocesses.
  If someone runs from a fresh checkout without `script/setup`,
  every integration row will be `no_tests` with a confusing error in
  the captured output.
- **`COMPAT_LATEST.md` is the auto-output file and is **not**
  gitignored.** A reviewer who re-runs `run_compat.py` should
  expect a working-tree change to `COMPAT_LATEST.md` (and `COMPAT.csv`)
  — flagged so future cleanup can decide whether to add it to
  `.gitignore` or include it as part of the committed deliverable.
- **`group_for_entry` side-channel (the recommended follow-up) is
  not a pure docs change.** It touches `router.py` (every
  `entry.data.get(SANDBOX_GROUP_KEY)` site becomes
  `data.group_for_entry.get(entry.entry_id)`) and `proxy_flow.py`
  (the CREATE_ENTRY path writes to the side-channel instead of
  `entry.data`). Small but real — not a one-line change. Flagged so
  whoever takes it on plans for that surface.
