Status: DONE

Phase 10 ships the testing infrastructure: two pytest plugins under
`sandbox_v2/hass_client/hass_client/testing/` (in-process +
real-subprocess) plus the `sandbox_v2/run_compat.py` lane runner that
drives them against `tests/components/<integration>/` directories.

The v1 wording in the plan ("drop-in `HomeAssistant` →
`RemoteHomeAssistant`") was reinterpreted for v2's subprocess
architecture. v2 has no `RemoteHomeAssistant` class — integration code
runs in a `SandboxRuntime` subprocess against its own private
`HomeAssistant`. The "fast compat" lane therefore can't swap a class;
instead it skips the subprocess by running `SandboxRuntime` as an
asyncio task on the test event loop and joining it to the manager-side
`Channel` via the in-memory loopback transport from `_inproc.py`. The
"real-websocket" lane was likewise reinterpreted — v2's transport is
stdio, not a websocket, so the equivalent is just letting the default
`SandboxManager` spawn the real `python -m hass_client.sandbox_v2`
subprocess. Both lanes share the same manager-side `SandboxBridge`
code path; the only thing that differs is how the channel pair is
materialised.

The in-process plugin's `async_setup_inprocess_sandbox()` is the
load-bearing helper. It calls `async_setup_component(hass,
"sandbox_v2", {})` to install the integration normally, then builds an
in-memory channel pair, constructs a `SandboxRuntime` with a one-shot
`channel_factory` that returns the runtime side, and pre-populates
`manager._sandboxes[group]` with an `_InProcessSandboxProcess`
stand-in that exposes the manager-side channel. The integration's
router and bridge code paths run unchanged — they think they're
talking to a real subprocess. One private-attribute access
(`manager._sandboxes`) is the only deviation from public API; flagged
inline with `# noqa: SLF001` and a comment.

The runtime task is created with `asyncio.create_task`, but
`create_task` schedules without entering the coroutine, so an
immediate `wait_until_ready` fails with `_ready is None`. The helper
yields with a `while not runtime.started: await asyncio.sleep(0)` poll
before calling `wait_until_ready(timeout=10)`, mirroring the polling
pattern in `tests/components/sandbox_v2/test_sandbox_runtime.py`.

The subprocess plugin's contribution is mostly the freezer detection:
`pytest_collection_modifyitems` adds a `pytest.mark.skip` to any test
whose `fixturenames` includes `freezer` or that's tagged
`@pytest.mark.no_sandbox_freezer`, and `pytest_configure` registers
the marker so `--strict-markers` accepts it. v1 silently fell back to
the in-process plugin when it detected `freezer`; v2 skips loudly so
the compat report shows the gap. No module-level socket monkey-patch
is needed — v2's transport is stdin/stdout pipes, not network sockets,
so v1's `pytest-socket` workaround simply has no v2 analogue.

`run_compat.py` is a stand-alone CLI that calls `uv run python -m
pytest -p <plugin> <test dir> --tb=no -q --no-header` for each
integration, parses pytest's summary line for passed/failed/errors/
skipped counts, and writes `COMPAT.csv` + `COMPAT.md`. Per-failure
output lands in `$SANDBOX_V2_ERRORS_DIR` (default
`/tmp/sandbox_v2_errors`). The runner is intentionally close in shape
to v1's `sandbox/run_all_sandbox_tests.py` so existing muscle memory
applies; the differences are (a) results live in `sandbox_v2/` not
`/tmp`, and (b) the markdown report is a first-class deliverable.

The plan's verification bullet — "compat suite passes ≥ v1's
baseline (878/880 = 99.8%)" — is **deferred to a Phase 10b sweep**.
Phase 10 ships the infrastructure; producing the actual baseline
needs the remaining 28 entity proxies Phase 5 deferred to Phase 5b
and a focused triage pass on per-integration failures. Mixing both in
this PR would have made review impossible.

Files added:
- `sandbox_v2/hass_client/hass_client/testing/__init__.py`
- `sandbox_v2/hass_client/hass_client/testing/_inproc.py`
- `sandbox_v2/hass_client/hass_client/testing/pytest_plugin.py`
- `sandbox_v2/hass_client/hass_client/testing/conftest_sandbox.py`
- `sandbox_v2/hass_client/tests/test_testing_inproc.py`
- `sandbox_v2/run_compat.py`
- `sandbox_v2/COMPAT.md`
- `tests/components/sandbox_v2/test_testing_plugins.py`

Files changed:
- `sandbox_v2/plan.md` — Phase 10 marked complete; per-bullet status +
  inline notes for the v1→v2 reinterpretations and the deferred
  baseline verification.

Core HA files modified (review surface):
- None. (Phase 10 is plugin-side and runner-side only; the
  manager-side `_sandboxes` access in the in-process plugin is a
  controlled internal hop covered by `# noqa: SLF001`.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **91 passed** (84 from Phase 0–9 + 7 new in
  `test_testing_plugins.py`).
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → **43 passed** (39 from Phase 0–9 + 4 new in
  `test_testing_inproc.py`).
- `uv run prek run --files <8 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, pylint, prettier).

Things to flag for the next phase:

- **The baseline compat pass is owed.** `run_compat.py` is wired and
  smoke-tested end-to-end (the `--help` invocation works, and the
  parser/writer paths are exercised by the runner-internal tests), but
  no integration has been run through it yet. A Phase 10b sweep should
  (a) run the v1 33-integration list, (b) record results in COMPAT.md,
  (c) triage every non-pass row into a category bucket (mirroring v1's
  TEST_RESULTS.csv shape), and (d) raise issues for each category
  ahead of the v1→v2 migration cut-over.
- **The in-process plugin auto-loads only the `built-in` sandbox
  group.** The `sandbox_v2_inprocess` fixture takes no parameters
  beyond `hass` and `tmp_path_factory`; tests that need a `main` or
  `custom` group must call `async_setup_inprocess_sandbox(group=...)`
  directly. Could be parametrised if a real compat run shows it
  matters.
- **Route-on-classify is not yet automatic.** The plugins set up the
  sandbox infrastructure, but a vanilla HA Core integration test's
  `MockConfigEntry` does not auto-tag itself with `__sandbox_group`,
  so the router's classifier path doesn't fire for entries the test
  itself creates. The compat lane therefore tests the bridge in
  isolation today; for end-to-end "integration X routes to built-in"
  coverage the runner would need a small monkey-patch that tags
  `MockConfigEntry.add_to_hass` to set `__sandbox_group` based on the
  classifier. Flagged because it's the obvious next-tightening once
  Phase 10b numbers exist.
- **`_InProcessSandboxProcess` does not implement the full
  `SandboxProcess` surface.** It exposes the two attributes
  (`state`, `channel`) the router actually reads plus a no-op
  `start`/`stop` and a best-effort `async_graceful_shutdown`. If a
  future phase grows the SandboxProcess interface (e.g., adds a
  `last_seen` for health protocol), the stand-in needs to keep up.
- **The freezer skip is fixture-name-based.** It triggers on any test
  that takes a parameter literally named `freezer` — pytest-freezer's
  default. A test that wraps `freezer` in another fixture won't be
  caught; flagged for tightening if false negatives show up. The
  marker (`@pytest.mark.no_sandbox_freezer`) is the documented escape
  hatch.
- **The CLI's `run_compat.py` lives at `sandbox_v2/` (script form),
  not as a package module.** Running `uv run python sandbox_v2/run_compat.py`
  works; the `# ruff: noqa: INP001` on the file is the documentation
  that this is intentional. If a future cleanup wants to make it
  `python -m sandbox_v2.run_compat`, the file would need to move
  under a package directory.
- **Per-integration error captures land in `/tmp` by default.** The
  `SANDBOX_V2_ERRORS_DIR` env var overrides the location; the runner
  creates the dir on first failure. Documented in COMPAT.md.
- **The runner takes a hard 5-minute per-integration timeout.** Same
  as v1; tunable via `--timeout`. If a real compat pass surfaces
  legitimately-slow integration suites, raise per-integration
  overrides via a config file rather than bumping the global default.
