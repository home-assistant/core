# Sandbox v2 — Follow-up phases (12–17)

The Phase 5–10 implementation landings each flagged work forward that
would have made the corresponding PR too large to review. Phase 11
shipped the architecture doc + decision log; Phases 12–17 are the
follow-ups that closed those forward-flags in turn. This file is the
**narrative** — the causal chain from one phase's deferral to the next
phase's landing.

Per-failure remediation entries live in [`BACKLOG.md`](../BACKLOG.md);
deep landing notes live in the per-phase `STATUS-phase-N.md` files in
the parent directory. FOLLOWUPS.md is the connective tissue between
them.

---

## Phase 12 — Concurrent channel dispatcher

**Why.** Phase 9 found that the single-threaded `Channel` reader
deadlocked when a handler re-entered with `channel.call(...)` — the
reply landed on the same reader that was busy dispatching the handler.
Phase 9 shipped restore_state in the shutdown reply as the specific
workaround, but `EVENT_HOMEASSISTANT_FINAL_WRITE` couldn't fire on
sandbox shutdown (it would re-enter `MSG_STORE_SAVE` on the same
channel), so any integration that relied on `delay_save` Stores
flushing on shutdown silently lost data.

**What landed.** Both `Channel` classes (HA-Core
`homeassistant/components/sandbox_v2/channel.py` and sandbox
`sandbox_v2/hass_client/hass_client/channel.py`) now dispatch each
inbound call or push in its own `asyncio.create_task`. A bounded
`asyncio.Semaphore` (default 16 in-flight, `max_inflight` keyword to
dial down) gates concurrent handlers but is acquired inside the
dispatched task, so the reader keeps draining the wire even when the
cap is hit. `SandboxRuntime._run_graceful_shutdown` now fires
`EVENT_HOMEASSISTANT_FINAL_WRITE` (after setting `CoreState.final_write`
and `await hass.async_block_till_done()`) so `delay_save` Stores flush
through `RemoteStore` before the reply goes out.

**Outcome.** 93 HA-core sandbox_v2 tests + 45 hass_client tests green
(2 new channel tests covering reentrancy + the concurrency cap; 2 new
shutdown tests covering FINAL_WRITE + `delay_save` flush). Phase 9's
"concurrent channel dispatcher" flag is closed.

**Files.** `channel.py` (both sides) + `sandbox.py` + `_helpers.py` +
`test_channel.py` + `test_shutdown.py`. No core HA files touched.

---

## Phase 13 — 28 remaining domain proxies

**Why.** Phase 5 shipped four entity proxies (`light`, `switch`,
`sensor`, `binary_sensor`) to prove the action-call forwarding path
end-to-end and keep the entity-bridge PR reviewable. The remaining 28
supported HA entity domains were called out as mechanical wrappers
around `SandboxProxyEntity` using the same `_call_service(...)`
pattern — small but plenty enough to drown an in-flight PR.

**What landed.** 28 new proxy classes under
`homeassistant/components/sandbox_v2/entity/` plus a `scene` symmetry
proxy (`scene` lives in `ALWAYS_MAIN` so it never routes through, but
the proxy exists so a future classifier change can't surprise us).
Each proxy subclasses `SandboxProxyEntity` + the domain's `*Entity`,
exposes domain-typed properties out of `_state_cache`, and translates
methods into `sandbox_v2/call_service` RPCs via the Phase 5 batcher.
Domains that index `supported_features` with `in` re-wrap the wire int
into the domain's `*EntityFeature` IntFlag in `__init__`; four whose
`state` is `@final` and reads a name-mangled private field (`button`,
`event`, `notify`, `scene`) override `sandbox_apply_state` to write
the mangled attribute directly so the parent's `@final` getter computes
the right state.

**Outcome.** `_DOMAIN_PROXIES` now dispatches every supported HA
entity domain. 121 HA-core sandbox_v2 tests green (28 new parametrised
smoke tests + 93 prior). `calendar`/`todo` listing and
`weather.async_forecast_*` flagged forward as query-shaped RPCs the
action-call channel can't express — these stay open and live in
[`BACKLOG.md`](../BACKLOG.md).

**Files.** 28 new `entity/<domain>.py` files + `entity/__init__.py`
dispatch table + `test_phase13_proxies.py`. No core HA files touched.

---

## Phase 14 — Schema marshalling, unique_id, unload hook, perf benchmark

**Why.** Phase 5 stripped `data_schema` on the wire (tagged
`_has_data_schema: True` for the future bridge) and didn't propagate
`unique_id` from the sandbox flow's `flow.context` back to the proxy,
so main's duplicate-detection guard couldn't fire. Phase 5 also left
the entry-unload path without a router hook (Phase 4 only intercepted
setup) and deferred the 200-light area-call benchmark because the
in-process tests couldn't measure the real transport.

**What landed.** `voluptuous_serialize.convert(..., custom_serializer=cv.custom_serializer)`
on the sandbox side ships the same list-of-fields shape the HA
frontend already renders; a `schema_bridge.reconstruct_schema` helper
on main rebuilds a permissive `vol.Schema` (primitives + `select` map
back precisely; everything else is a pass-through since the sandbox
runs the real validator on every call). The same bridge applies to
service schemas: `ServiceMirror` now pushes the serialised schema with
every `register_service` so main rejects bad service-call input
without round-tripping. `unique_id` rides in the marshalled
`FlowResult.context` (looked up via `flow_manager.async_get(flow_id)`
because FORM / SHOW_PROGRESS results don't carry context themselves)
and the proxy applies it via `await self.async_set_unique_id(...)`.
`ConfigEntries.async_unload` consults `router.async_unload_entry`
before falling through — same shape as Phase 4's setup intercept. The
perf benchmark spins up the in-process plugin (real channel-pair +
JSON encode/decode + batcher), registers 200 proxy lights,
area-targets `light.turn_on`, and asserts the batcher coalesces 200
entity invocations into ≤2 RPCs in under 500 ms.

**Outcome.** 133 HA-core sandbox_v2 tests + 46 hass_client tests + 383
core `test_config_entries.py` + 30 core `test_entity_component.py`
green. Phase 5's four deferrals (`data_schema`, `unique_id`,
`async_unload_entry`, perf) all closed.

**Files.** `schema_bridge.py` (both sides) + `bridge.py` +
`proxy_flow.py` + `flow_runner.py` + `service_mirror.py` +
`test_phase14.py` + `test_perf.py`. **Core HA:**
`config_entries.py` — `ConfigEntryRouter` Protocol gains
`async_unload_entry`; `ConfigEntries.async_unload` consults it before
the existing path. Same minimal-hook shape as the Phase 4 setup
intercept; the Phase 4 `router` attribute is reused.

---

## Phase 15 — v1-baseline compat sweep (10b)

**Why.** Phase 10 shipped the test infrastructure (two pytest plugins
+ `run_compat.py`) but deferred the actual v1-baseline run. The
runner needed (a) the remaining 28 proxies (Phase 13), (b) two
plumbing fixes — `cwd` was wrong for HA-core test conftest imports and
the pytest-cov hook needed `--no-cov` — and (c) a `MockConfigEntry`
autotag patch so the classifier path fires for entries the tests
themselves create (otherwise the bridge code paths never run during
the integration's own test suite).

**What landed.** A sync classifier mirror in
`sandbox_v2/hass_client/hass_client/testing/_autotag.py` (mirrors the
Phase 2 classifier's five-rule order; the async real classifier
can't run from inside an already-on-the-loop test). Both pytest
plugins install the patch in `pytest_configure` and tear down in
`pytest_unconfigure`. `run_compat.py` switched `cwd` to `CORE_ROOT`
and passes `--no-cov`; its default markdown output moved to
`COMPAT_LATEST.md` so ad-hoc runs don't overwrite the curated
`COMPAT.md` baseline report.

**Outcome.** 29 of 37 integrations fully pass; **7,586/7,648 tests
pass = 99.19 %** at the test level. Every one of the 62 failures
buckets into a single `test-only` root cause: the autotag patch
mutated `entry.data` to add `__sandbox_group: built-in`, which a
handful of helper integrations (`group`, `template`, `min_max`,
`derivative`, `threshold`, `utility_meter`, `integration`, `proximity`)
inspect directly (assertions like `entry.data == {}`, or Syrupy
snapshots). Confirmed by re-running the same files without the
sandbox plugin: 107/107 pass. Below the 99.5 % v1-removal threshold —
the recommended fix Phase 15 flagged is what became Phase 17.

**Files.** `_autotag.py` + `pytest_plugin.py` + `conftest_sandbox.py`
+ `run_compat.py` + `COMPAT.md` + `COMPAT.csv` + tests. No core HA
files touched.

---

## Phase 16 — Cross-integration sweep + categorised backlog

**Why.** Phase 15 covered v1's 37-integration list. The plan called
for the full classifier-routable set so we'd see whether the autotag
noise scaled, whether other buckets emerged at scale, and whether any
classifier or `ALWAYS_MAIN` changes were warranted across the broader
universe of HA integrations.

**What landed.** `run_compat_full.py` — asyncio + JUnit XML + outer
concurrency, forked rather than extended from `run_compat.py` because
the runner shape is different (asyncio vs sync-subprocess loop; JUnit
XML vs text parsing; outer concurrency vs serial) and the Phase 15
runner has to stay stable for the curated 37-integration report.
`categorize_failures.py` walks the captured JUnit failures with an
ordered regex rule set (first-hit-wins, most-specific → most-generic)
into named buckets — `test-only`, `dependencies-not-shared`,
`proxy-missing`, `protocol-gap`, `unknown`, etc. `generate_backlog.py`
produces a draft skeleton; the committed `BACKLOG.md` is hand-curated
on top.

**Outcome.** **807** integrations exercised in **705s wall** at
concurrency=6 (well inside the 30–90 min budget the plan called out).
561/807 pass cleanly; 33 714/34 378 tests pass = **98.07 %**
test-level. Categoriser hit rate 98.6 % (clearing the ≥95 % gate).
**640 of 664 failures (96.4 %) are the same `__sandbox_group` autotag
noise Phase 15 already flagged**, just amplified — the single highest-
leverage fix in the entire v2 codebase. Two real bridge findings,
both scoped to two integrations: `dependencies-not-shared` (10
failures on `azure_event_hub` + `atag`) and `proxy-missing` (5
failures on `atag`). Both turned out to be autotag perturbation in
Phase 17, not real bridge bugs.

**Files.** `run_compat_full.py` + `categorize_failures.py` +
`generate_backlog.py` + `COMPAT_FULL.md` + `COMPAT_FULL.csv` +
`BACKLOG.md` + `BACKLOG_FAILURES.json`. No core HA files touched.

---

## Phase 17 — `ConfigEntry.sandbox` first-class field

**Why.** Phase 15 and Phase 16 both identified the same single highest-
leverage fix: move the sandbox-group routing tag off `entry.data` onto
a dedicated first-class field. The autotag patch mutating `entry.data`
to add `__sandbox_group: built-in` was being observed by 96.4 % of
every failure across 807 integrations (552 of 664) — every Syrupy
snapshot that included `entry.data` and every test assertion like
`entry.data == {}`.

**What landed.** Optional `ConfigEntry.sandbox: str | None` field on
`homeassistant/config_entries.py` — additive, no storage version bump,
optional read on load so pre-existing stored entries reconstruct with
`sandbox=None`. Plumbed via `as_dict()` (writes only when non-None) +
`async_update_entry(entry, sandbox=)` + the existing
`UPDATE_ENTRY_CONFIG_ENTRY_ATTRS` set. The plan's "call
`async_update_entry(entry, sandbox=group)` right after the framework
creates the entry" approach hit an order-of-ops gap (`async_add` runs
`async_setup` inside its own body, which consults the router; the
after-hook fires too late). The fix that works is to attach
`sandbox=<group>` to the `ConfigFlowResult` on the CREATE_ENTRY path so
`ConfigEntriesFlowManager.async_finish_flow`'s entry constructor reads
it via `result.get("sandbox")` — same plumbing shape `minor_version` /
`options` / `subentries` already use. V2 read sites in `router.py` and
`proxy_flow.py` consult `entry.sandbox`; the autotag patch sets
`entry.sandbox` via `object.__setattr__` instead of mutating
`entry.data`. `SANDBOX_GROUP_KEY` is fully gone.

**Outcome.** Curated 37-integration baseline **99.19 % → 99.97 %**
(35/37 integrations pass; 2 residual diagnostic snapshots). Full
807-integration sweep **98.07 % → 99.67 %** — clears the 99.5 %
v1-removal threshold the plan asked for. **552 of the 664 known
failures closed in one fix.** Every named bridge bucket
(`proxy-missing`, `dependencies-not-shared`, `protocol-gap`, ...) is
**at zero**. The atag `proxy-missing` and `dependencies-not-shared`
rows Phase 16 flagged as "the microcosm of every remaining real-bug
bucket" vanished without touching `bridge.py` — they were autotag-
fixture perturbation, not real bridge bugs. 112 residual failures are
**100 % test-side**: ~30 diagnostic snapshots showing
`+ 'sandbox': 'built-in'`, ~70 `'created_at'` snapshot drift on tests
that didn't pin the wall clock, 5 environmental rows from Phase 16.

**Files.** Core HA: `config_entries.py` (additive field + flow-result
plumbing). V2: `router.py` + `proxy_flow.py` + `_autotag.py` +
`categorize_failures.py`. Tests: `tests/common.py` (`MockConfigEntry`
gets `sandbox=` kwarg) + 6 new `tests/test_config_entries.py` cases +
v2 test updates. Reports: `COMPAT.md` + `COMPAT_FULL.md` + `BACKLOG.md`
+ `BACKLOG_FAILURES.json` + companion `.csv` files all regenerated.

---

## Still open

These are the items that survived Phase 17 — see
[`../CLAUDE.md`](../CLAUDE.md)'s "Open follow-ups" section for the
same list with deeper context, and [`../BACKLOG.md`](../BACKLOG.md)
for the per-failure-category remediation table.

- **`share_states=True` subscription consumer + main-side filtering.**
  The config knob is wired; the consumer that opens a subscription
  back to main and the filtering on main's emit path are owed in the
  same PR. Carried untouched from Phase 7.
- **v1 removal.** The numeric gate (Phase 11) is now satisfied —
  Phase 17 cleared the 99.5 % threshold. Remaining condition is "v2
  has shipped at least one stable release," a release-process step
  rather than a code change.
- **Diagnostic snapshot drift / clock-pinning.** ~30 integrations
  show `+ 'sandbox': 'built-in'` in their diagnostic snapshots (fix
  is `pytest --snapshot-update` per integration); ~70 show
  `created_at` drift on tests that didn't pin the wall clock
  (integration-side freezegun, or an optional Phase 17b clock-pinning
  fixture on the compat plugin — ~30 LOC, sketched in BACKLOG.md).
- **`calendar` / `todo` / `weather` query-shaped RPCs.** The Phase 13
  proxies return empty lists for `async_get_events`, `todo_items`,
  and `weather.async_forecast_*` because the action-call channel
  can't express server-side queries. Add a query-shaped RPC if the
  compat sweep ever surfaces an integration that depends on these
  surfaces.
- **Non-idempotent service handlers** (`ai_task`, `image`).
  `ALWAYS_MAIN` punt for v2; v3 spec on service-handler-level
  interception or sandbox-aware integration hooks. See the Phase 1
  spike doc.

For per-failure remediation (residual `test-only` failures, the rare
`unknown` bucket entries, environmental rows) see
[`../BACKLOG.md`](../BACKLOG.md).
