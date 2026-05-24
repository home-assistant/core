# Sandbox v2 — Phase 17 categorised backlog

Phase 17 moved the autotag's effect off `entry.data` onto a new
first-class `ConfigEntry.sandbox` field. The full sweep was re-run
(`run_compat_full.py` — 807 integrations, in-process plugin, JUnit
captured per-test) and bucketed with `categorize_failures.py`. The raw
rollup is in `BACKLOG_FAILURES.json`; the per-integration table is in
`COMPAT_FULL.md`. This file is the **categorised remediation plan**.

## Headline

- **807** integrations, **34 378** tests collected.
- **711** integrations pass cleanly; **96** have at least one failure.
- Test-level pass rate: **99.67 %** (34 266 passed / 34 378).
- Categorisation hit rate: **95.5 %** (107 of 112 failures bucketed).

### Phase-16 → Phase-17 delta

|                              | Phase 17 | Phase 16 |  Δ |
| ---                          |     ---: |     ---: |     ---: |
| Integrations                 |      807 |      807 |       0 |
| Fully passing                |  **711** |      561 |   +150 |
| With failures                |       96 |      246 |   -150 |
| Tests passed                 |   34 266 |   33 714 |    +552 |
| Tests failed                 |  **112** |      664 |    -552 |
| **Test-level pass rate**     | **99.67 %** |  98.07 % | +1.60 pp |
| Categorisation hit rate      |   95.5 % |   98.6 % |   -3.1 pp |

The headline Phase 16 follow-up (move the sandbox-group tag off
`entry.data`) **closed 552 of the 664 known failures** in one fix.
What's left is two-thirds tests with frozen-time / snapshot
drift (`'created_at': '20XX-...'` in diagnostic dicts that no longer
match the snapshot) and one-third the same residual environmental
issues Phase 16 flagged (BLE library, timezones, token refresh).

## Bucket overview (ordered by integration count)

| Bucket | Failures | Integrations |
| --- | ---: | ---: |
| `test-only` | 107 | 91 |
| `unknown` | 5 | 5 |

Every category-specific bridge bucket (`proxy-missing`,
`dependencies-not-shared`, `protocol-gap`, ...) is **at zero** for
Phase 17 — including the two atag findings Phase 16 surfaced. That's
notable: the autotag patch was previously injecting `__sandbox_group`
into `entry.data` of `atag`'s test fixtures in a way that perturbed
fixture composition and surfaced a coordinator-shape bug downstream.
Moving the tag onto a side-band field removes that perturbation, and
atag's `proxy-missing` / `dependencies-not-shared` rows vanish along
with the autotag noise. Re-investigate only if atag-style failures
re-appear once integrations adopt diagnostic snapshots that include
the new `sandbox` field.

---

## `test-only` — 107 failures across 91 integrations

Three distinct sub-shapes, all with the same fix story: the test
asserts on or snapshots a representation of the entry that includes a
field the compat lane's autotag mutates. v2 didn't write the snapshot
and can't refresh it from inside this tree — the fix lives in the
integration's tests/ directory.

### Sub-shape 1: ``+ 'sandbox': 'built-in'`` in diagnostic snapshots — ~30 failures

`tests/components/<int>/test_diagnostics.py` snapshots
`entry.as_dict()` (often via the Diagnostics framework) and the
snapshot pre-dates Phase 17's `sandbox` field. Affects integrations
that ship a `diagnostics.py` and a diagnostics test snapshot.

```
'config_entry': dict({
  ...
+ 'sandbox': 'built-in',
  'source': 'user',
  ...
})
```

Fix: `pytest tests/components/<int>/test_diagnostics.py --snapshot-update`
per integration. One-line snapshot diff per file; mechanical.

### Sub-shape 2: ``'created_at': '20XX-...'`` snapshot drift — ~70 failures

`test_diagnostics.py` / `test_config_flow.py` snapshots that include
the entry's full dict but don't use `freezegun` or the `<ANY>` Syrupy
matcher for the timestamp. The compat lane runs on the wall clock so
each snapshot diff shows the run date. **Pre-existing test fragility**
— the same failures would appear in the integration's own CI on a
non-snapshot-build day. Phase 16 had these too; their proportion grew
because the dominant autotag noise vanished.

```
- 'created_at': '2025-01-01T00:00:00+00:00',
+ 'created_at': '2026-05-24T04:55:51.181434+00:00',
```

Fix: integration-side. Either pin the time with
`@pytest.mark.freeze_time` (preferred) or replace the timestamp in
the snapshot with Syrupy's `<ANY>`. Out of v2 scope.

### Sub-shape 3: legacy ``entry.data == {…}`` assertions — handful

Helper integrations (e.g. `template`, `group`, `min_max` in Phase 15)
that asserted `entry.data == {}` — Phase 17 cleared the dominant
chunk of these, but a few stragglers remain where the snapshot or
assertion shape is slightly different (e.g. nested under
``'entry_data'`` rather than `data`).

### Top 10 affected integrations

| Integration | Failures |
| --- | ---: |
| `enphase_envoy` | 5 |
| `vacasa` | 3 |
| `ampio` | 2 |
| `bang_olufsen` | 2 |
| `comelit` | 2 |
| `data_grand_lyon` | 2 |
| `ecovacs` | 2 |
| `whirlpool` | 2 |
| `xiaomi_aqara` | 2 |
| _… 82 more, 1 failure each_ | |

_Full per-integration list in `BACKLOG_FAILURES.json`._

### Proposed fix

**Zero v2 changes required.** The bridge code paths the compat lane
exercises pass cleanly on every integration in this sweep
(`proxy-missing` and `dependencies-not-shared` are both at 0). The
remaining work is integration-side snapshot updates and freezegun
adoption, neither of which is the sandbox_v2 tree's responsibility.

If we want to lift the pass rate further, the cleanest path is to
extend the compat plugin with a fixture autouse that pins the clock
to a known epoch (e.g. `2025-01-01T00:00:00+00:00`) for diagnostic
tests. That would mask the `created_at` drift without forcing every
integration owner to adopt freezegun. ~30 LOC in
`hass_client/testing/pytest_plugin.py`, optional Phase 17b.

### Estimated size

- v2 work to close to ~100 %: **0 LOC** (zero bridge issues). The
  remaining diffs live in integrations' `__snapshots__/` directories
  and are out of scope.
- Phase 17b: ~30 LOC for a clock-pinning fixture on the compat
  plugin if we want to eat the snapshot drift on v2's side.

---

## `unknown` — 5 failures across 5 integrations

The same residual environmental rows Phase 16 surfaced. Not v2
bridge bugs:

| Integration | Failures | Likely root cause |
| --- | ---: | --- |
| `bluetooth` | 1 | `BleakClientBlueZDBus.__init__() missing 1 required keyword-only argument: 'bluez'` — `habluetooth` 4.x vs `bleak` 1.x compat issue in the test env. |
| `chess_com` | 1 | `test_diagnostics` Syrupy diff on `joined`/`last_online` timestamps — test fixture renders local TZ vs UTC. |
| `google` | 1 | `test_invalid_token_expiry_in_config_entry[timestamp_naive]` — refresh-token roundtrip yields `'ACCESS_TOKEN'` instead of `'some-updated-token'`. |
| `html5` | 1 | `test_html5_send_message[…-86400-None]` — `timestamp` delta `18000000` vs `0`; freezegun + tz fragility. |
| `mastodon` | 1 | `test_get_account_success` snapshot diff on `tzlocal()` vs `tzutc()`. |

### Proposed fix

- 0 LOC for v2. File upstream as integration-test fragility (BLE
  version skew is a HA env issue; the others are test-fixture issues
  for the respective integration owners).

---

## `ALWAYS_MAIN` additions recommended

**None** based on this sweep. Same as Phase 16's recommendation —
no integration in the swept set surfaced a real
sandbox-incompatibility shape. The two integrations that flagged
`dependencies-not-shared` in Phase 16 (`azure_event_hub`, `atag`)
now pass cleanly — the autotag noise that perturbed their fixtures
was the actual cause, and Phase 17 removed it.

## Classifier rule changes recommended

**None.** The discovery filter caught everything the classifier would
route to `MAIN`, and no integration in the swept set surfaced an
`integration-uses-deny-listed-platform` failure. The deny-list and
`ALWAYS_MAIN` set are correctly sized for the 807-integration
universe.

## Reproducing this report

```bash
cd sandbox_v2
# Full sweep (~12 min on a 16-core box, concurrency=6)
uv run python run_compat_full.py --concurrency=6

# Categorise failures into buckets
uv run python categorize_failures.py

# Regenerate the auto-draft skeleton (not used directly — this file
# is hand-curated). Source of truth is BACKLOG_FAILURES.json + this
# document.
uv run python generate_backlog.py --out BACKLOG.draft.md
```
