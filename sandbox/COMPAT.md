# Sandbox compat report

Phase 17 baseline. This file is the **curated** reviewer-facing report
— `run_compat.py` writes its raw per-run summary to `COMPAT_LATEST.md`
and `COMPAT.csv`, never to `COMPAT.md`.

## Status

**Phase 17 baseline (in-process plugin, 2026-05-24)** — 37-integration
set lifted from v1's `hass_client/SANDBOX_COMPAT.md`. Phase 17 moved
the sandbox-group tag off `entry.data` onto the new first-class
`ConfigEntry.sandbox` field, eliminating the autotag's
`entry.data == {}` and `+ '__sandbox_group'` snapshot noise.

|                              | v2 (Phase 17) | v2 (Phase 15) | v1 (baseline) |
| ---                          |          ---: |          ---: |          ---: |
| Integrations                 |            37 |            37 |            37 |
| Fully passing                |            35 |            29 |            35 |
| With failures                |             2 |             8 |             2 |
| Tests passed                 |         7,646 |         7,586 |           955 |
| Tests failed                 |             2 |            62 |             2 |
| Test errors                  |             0 |             0 |             0 |
| Tests skipped                |            17 |            17 |             0 |
| **Test-level pass rate**     |    **99.97%** |    **99.19%** |    **99.79%** |

The Phase 17 run climbs from 99.19 % to **99.97 %**, clearing the
99.5 % v1-removal threshold the plan asks for. The two remaining
failures (proximity, utility_meter) are both diagnostic-snapshot
diffs that report `+ 'sandbox': 'built-in'` at the top level of
`entry.as_dict()` — the autotag is still tagging the entry, the new
`sandbox` field is now visible in diagnostics output, and the
pre-Phase-17 snapshots don't include it. The fix is one
snapshot-update per integration (out of v2's scope; it lives in the
integration's tests/).

## Bucketed triage

| Bucket               | Count | Why |
| ---                  |   ---: | --- |
| `test-only` (autotag-induced) | 2 | Diagnostic snapshots that include the entry's full `as_dict()` — the new `sandbox` field surfaces and the pre-Phase-17 snapshot doesn't expect it. |
| `proxy-missing`      |     0 | All 32 domains have proxies after Phase 13. |
| `protocol-gap`       |     0 | Phase 14's voluptuous-serialize bridge + `unique_id` propagation cleared the known gaps. |
| `integration-incompat` |   0 | No integration in the v1 set hit `ALWAYS_MAIN`/deny-list paths. |

### Why the remaining failures are `test-only`

Phase 17 moved the autotag's effect off `entry.data` onto the new
first-class `ConfigEntry.sandbox` field. The two remaining failures
both happen in `test_diagnostics.py` files that include
`entry.as_dict()` in their snapshot, e.g. `proximity` and
`utility_meter`. The diagnostic now reports `+ 'sandbox': 'built-in'`
at the top level. The bridge half is unchanged from a successful pass;
only the snapshot needs a refresh.

Per-failure pytest output for each `issues` row lives under
`${SANDBOX_V2_ERRORS_DIR:-/tmp/sandbox_errors}/<integration>.txt`.

## Recommendation

The 99.97 % test-pass rate **clears the 99.5 % v1-removal threshold**
the plan calls out. Phase 17 closes the dominant
test-noise bucket Phase 15 / Phase 16 surfaced; the residual diff is
two diagnostic snapshots that would update with one
`pytest --snapshot-update tests/components/{proximity,utility_meter}/`.
That update is out of v2's scope — the snapshots live in the
respective integrations' test trees, not under `sandbox/`.

The bridge code paths the compat lane exercises — router setup,
entity proxies (all 32 domains), service mirror, event mirror,
restore_state warm-load, schema bridge — pass cleanly on every
integration in this run.

### Where this leaves v1 removal

The numeric trigger Phase 15 set ("v2 matches v1's compat numbers and
clears ≥ 99.5 %") is now satisfied. Phase 11's deferred
v1-removal item can be re-evaluated; the remaining condition the plan
attaches to it ("v2 has shipped at least one stable release") is a
release-process step rather than a code change.

## How to read this

Each integration row reflects one `pytest tests/components/<integration>/`
run with the sandbox plugin active. Statuses:

- **`pass`** — every collected test passed.
- **`issues`** — at least one failure or error. The pytest output is
  written to `${SANDBOX_V2_ERRORS_DIR:-/tmp/sandbox_errors}/<integration>.txt`
  so reviewers can dig in.
- **`timeout`** — the integration hit the per-run timeout (default 5 min).
  Often signals an integration that needs deny-listing (e.g. it spawns
  threads the sandbox doesn't model) or a real bug in the bridge.
- **`no_tests`** — `pytest` collected zero tests. Usually means the
  integration only ships a `test_config_flow.py` or similar and not a
  `test_init.py`; the runner still records the row so a later sweep can
  add coverage.

## Per-integration results (Phase 17 baseline)

Plugin: `hass_client.testing.pytest_plugin`

| integration | status | passed | failed | errors | skipped |
| --- | --- | ---: | ---: | ---: | ---: |
| input_boolean | pass | 18 | 0 | 0 | 0 |
| input_button | pass | 15 | 0 | 0 | 0 |
| input_datetime | pass | 28 | 0 | 0 | 0 |
| input_number | pass | 24 | 0 | 0 | 0 |
| input_select | pass | 26 | 0 | 0 | 0 |
| input_text | pass | 23 | 0 | 0 | 0 |
| counter | pass | 751 | 0 | 0 | 0 |
| timer | pass | 877 | 0 | 0 | 0 |
| schedule | pass | 387 | 0 | 0 | 0 |
| zone | pass | 32 | 0 | 0 | 0 |
| tag | pass | 12 | 0 | 0 | 0 |
| group | pass | 392 | 0 | 0 | 0 |
| person | pass | 34 | 0 | 0 | 0 |
| scene | pass | 41 | 0 | 0 | 0 |
| todo | pass | 281 | 0 | 0 | 0 |
| automation | pass | 117 | 0 | 0 | 0 |
| script | pass | 64 | 0 | 0 | 0 |
| alert | pass | 18 | 0 | 0 | 0 |
| template | pass | 2470 | 0 | 0 | 0 |
| plant | pass | 11 | 0 | 0 | 0 |
| proximity | issues | 27 | 1 | 0 | 0 |
| min_max | pass | 20 | 0 | 0 | 0 |
| statistics | pass | 56 | 0 | 0 | 0 |
| utility_meter | issues | 94 | 1 | 0 | 0 |
| derivative | pass | 76 | 0 | 0 | 0 |
| integration | pass | 61 | 0 | 0 | 0 |
| generic_thermostat | pass | 114 | 0 | 0 | 0 |
| generic_hygrostat | pass | 76 | 0 | 0 | 0 |
| history_stats | pass | 55 | 0 | 0 | 0 |
| threshold | pass | 114 | 0 | 0 | 0 |
| filter | pass | 32 | 0 | 0 | 0 |
| mqtt_statestream | pass | 17 | 0 | 0 | 0 |
| recorder | pass | 932 | 0 | 0 | 17 |
| rest | pass | 128 | 0 | 0 | 0 |
| logbook | pass | 106 | 0 | 0 | 0 |
| command_line | pass | 78 | 0 | 0 | 0 |
| trend | pass | 39 | 0 | 0 | 0 |

## Reproducing this report

```bash
cd sandbox

# Phase 15 baseline (v1's 37-integration list, in-process plugin)
uv run python run_compat.py \
  input_boolean input_button input_datetime input_number input_select input_text \
  counter timer schedule zone tag group person scene todo automation script \
  alert template plant proximity min_max statistics utility_meter derivative \
  integration generic_thermostat generic_hygrostat history_stats threshold \
  filter mqtt_statestream recorder rest logbook command_line trend

# Default: in-process plugin, every component with tests
uv run python run_compat.py

# Restrict to specific integrations
uv run python run_compat.py input_boolean light switch

# Use the real-subprocess plugin (slower; freezer tests auto-skipped)
uv run python run_compat.py --plugin subprocess
```

`run_compat.py` writes its per-run table to `COMPAT_LATEST.md` (not
`COMPAT.md`), so this curated baseline survives ad-hoc runs.

## Plugins

Two pytest plugins are wired up — see
`hass_client/hass_client/testing/`:

| Plugin | Wire | When to use |
| --- | --- | --- |
| `hass_client.testing.pytest_plugin` (in-process) | in-memory channel pair | fast feedback, freezer-safe |
| `hass_client.testing.conftest_sandbox` (subprocess) | real stdio JSON-line | pins the subprocess boundary, freezer tests auto-skip |

Both plugins install the `MockConfigEntry.add_to_hass` autotag patch
in `pytest_configure` so the router's classifier path fires for
entries the integration test itself creates. Phase 17 moved the tag
from a synthetic key in `entry.data` to the first-class
`ConfigEntry.sandbox` field, so the patch is now invisible to tests
that assert on `entry.data` shape. See
`sandbox/hass_client/hass_client/testing/_autotag.py`.
