# Sandbox — Follow-up phases (12–17)

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
`homeassistant/components/sandbox/channel.py` and sandbox
`sandbox/hass_client/hass_client/channel.py`) now dispatch each
inbound call or push in its own `asyncio.create_task`. A bounded
`asyncio.Semaphore` (default 16 in-flight, `max_inflight` keyword to
dial down) gates concurrent handlers but is acquired inside the
dispatched task, so the reader keeps draining the wire even when the
cap is hit. `SandboxRuntime._run_graceful_shutdown` now fires
`EVENT_HOMEASSISTANT_FINAL_WRITE` (after setting `CoreState.final_write`
and `await hass.async_block_till_done()`) so `delay_save` Stores flush
their pending writes to main before the reply goes out.

**Outcome.** 93 HA-core sandbox tests + 45 hass_client tests green
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
`homeassistant/components/sandbox/entity/` plus a `scene` symmetry
proxy (`scene` lives in `ALWAYS_MAIN` so it never routes through, but
the proxy exists so a future classifier change can't surprise us).
Each proxy subclasses `SandboxProxyEntity` + the domain's `*Entity`,
exposes domain-typed properties out of `_state_cache`, and translates
methods into `sandbox/call_service` RPCs via the Phase 5 batcher.
Domains that index `supported_features` with `in` re-wrap the wire int
into the domain's `*EntityFeature` IntFlag in `__init__`; four whose
`state` is `@final` and reads a name-mangled private field (`button`,
`event`, `notify`, `scene`) override `sandbox_apply_state` to write
the mangled attribute directly so the parent's `@final` getter computes
the right state.

**Outcome.** `_DOMAIN_PROXIES` now dispatches every supported HA
entity domain. 121 HA-core sandbox tests green (28 new parametrised
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

**Outcome.** 133 HA-core sandbox tests + 46 hass_client tests + 383
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
`sandbox/hass_client/hass_client/testing/_autotag.py` (mirrors the
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
leverage fix in the entire sandbox codebase. Two real bridge findings,
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
`options` / `subentries` already use. Read sites in `router.py` and
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
plumbing). Sandbox: `router.py` + `proxy_flow.py` + `_autotag.py` +
`categorize_failures.py`. Tests: `tests/common.py` (`MockConfigEntry`
gets `sandbox=` kwarg) + 6 new `tests/test_config_entries.py` cases +
sandbox test updates. Reports: `COMPAT.md` + `COMPAT_FULL.md` + `BACKLOG.md`
+ `BACKLOG_FAILURES.json` + companion `.csv` files all regenerated.

---

## plan-sandbox-context — `current_sandbox` contextvar replaces the store rebinding

**Why.** Phase 8 routed sandbox `Store` IO to main by rebinding
`homeassistant.helpers.storage.Store` at module scope — the `remote_store`
installer swapped in a `Store` subclass for the lifetime of the process. That
is the exact "do not monkey-patch private internals" smell the project's Iron
Law calls out — the same shape v1 was the cautionary tale for. It also had a
footgun: helpers that did `from .storage import Store` at import time
(`restore_state`, the registries) captured the *original* class, so the
rebinding couldn't reach them — `restore_state` needed an explicit per-instance
`Store` swap as a workaround.

**What landed.** A declared core HA hook: `current_sandbox`, a module-level
`ContextVar[SandboxBridge | None]` in
`homeassistant/helpers/sandbox_context.py`, read by `Store._async_load_data`,
`Store._async_write_data`, and `Store.async_remove` at IO time. A contextvar
read inside the instance methods is a single source of truth no matter how
`Store` was imported, so the `restore_state` workaround is gone. The sandbox
runtime sets the contextvar to a `ChannelSandboxBridge` before the warm-load;
asyncio's context copy on `create_task` propagates it to every handler. Shipped
as **A1** (additive — contextvar branch alongside the rebinding) then **A2**
(deleted `remote_store.py`, the installer, and the `restore_state` swap). A2's
load-bearing detail: the save branch lives at `_async_write_data`, not
`async_save`, so `async_delay_save` and the FINAL_WRITE flush — which bypass
`async_save` — route to main too.

**Outcome.** Zero patched globals in the sandbox; `Store` routing is a declared
hook. The "monkey-patch the storage module" tension is closed.

---

## plan-strip-auth-scopes — revert the Phase-7 `RefreshToken.scopes` mechanism

**Why.** Phase 7 added `RefreshToken.scopes` + a websocket-dispatcher
`_scope_allows` check across four core HA files
(`auth/models.py`, `auth/__init__.py`, `auth/auth_store.py`,
`websocket_api/connection.py`) plus a persisted `scopes` key in the
on-disk auth store. It was built for a sandbox→main websocket that was
never wired up, so no code path ever exercised the scope check
end-to-end — the feature was asserted only by an isolated dispatcher
test. Phase 20 had already deleted the `share_*` opt-in that paired with
scope-as-deny, leaving scopes guarding a non-existent attack surface.
That's permanent core surface for zero current value.

**What landed.** The whole `scopes` mechanism reverted from core HA. The
sandbox still gets a dedicated system user per group and an access token
freshly minted on each spawn — only the scoping disappears.
`_get_or_create_sandbox_refresh_token` now identifies the token by the
one-token-per-system-user invariant instead of matching a scope set.
Back-compat: the auth-store load path pops a legacy `scopes` key if
present (option A — silent drop, no storage-version bump), covered by a
regression test; the sandbox is unreleased so the only on-disk scoped tokens are
dev machines on this branch.

**Outcome.** Core HA's auth surface is back to its pre-Phase-7 shape; the
sandbox core-HA touch list shrinks from four surfaces to three.
[`auth-scoping-decision.md`](auth-scoping-decision.md) is kept as a
SUPERSEDED design record for the eventual re-introduction.

---

## plan-auth-context — drop the unused token + system user, restore context

**Why.** Two design-review simplifications. (1) The manager minted a
per-group system-user access token and passed it on `--token`; the
runtime stored it (`SandboxRuntime.token`) and **never used it** — the
sandbox is not an authenticated principal inside main and never connects
back, so the credential was dead weight (same reasoning as
`plan-strip-auth-scopes`). (2) Main's handling of an inbound `context_id`
was incomplete: it minted a fresh `Context` per echo (adopting the
sandbox's id and attributing it to the per-group system user), dropping
the original attribution of a user-initiated action that flowed
main → sandbox → back.

**What landed (Parts A/B/C).**
- **A — token gone end-to-end.** No `--token` argv (`manager._default_command`),
  no `SandboxRuntime.token` field/param, no `SANDBOX_TOKEN` in the Docker
  entrypoint / compose / docs, no `async_issue_sandbox_access_token`.
- **C — system user gone.** `auth.py` deleted entirely;
  `bridge._async_system_user_id` / `_system_user_id` removed. Genuinely
  sandbox-originated contexts are now `user_id=None` — the honest shape,
  since no user authored them.
- **B — context restoration.** The bridge seeds a `context_id → Context`
  cache at every main→sandbox **call-down** site (the service forwarder
  `_forward`, and the proxy entity's `async_call_service`, which now
  threads the entity's live `Context`). A 15-minute TTL bounds it (volume
  is tiny — a forwarded context is echoed back within the same operation).
  `_resolve_context` returns a cached Context verbatim for a known id
  (restoring `parent_id` / `user_id`), and for an unknown/expired id mints
  a **brand-new** `Context(user_id=None)` with main's **own** trusted id —
  never the sandbox-supplied ULID, whose embedded timestamp main can't
  trust (recorder/logbook order by it). A miss is always safe.

**Outcome.** The sandbox provably cannot fabricate attribution: the wire
carries only a `context_id` string, and main owns every `Context` it
produces. The sandbox core-HA touch list is unchanged (this is all inside the
integration + runtime). A richer audit answer — a `Context` group
attribute — is left as a follow-up below.

---

## Still open

These are the items that survived Phase 17 — see
[`../CLAUDE.md`](../CLAUDE.md)'s "Open follow-ups" section for the
same list with deeper context, and [`../BACKLOG.md`](../BACKLOG.md)
for the per-failure-category remediation table.

- **State-sharing subscription consumer + main-side filtering.**
  Phase 20 deleted the unwired `SharingConfig` / `SandboxGroupConfig`
  surface and replaced it with a design doc
  ([`design-share-states.md`](design-share-states.md)) covering the
  entity_id alignment constraint, the `share/subscribe_*` protocol,
  the main-side filter, and the open questions. The actual consumer
  is owed in a future phase against that design.
- **Re-introduce a sandbox credential (with scopes) when the WS lands.**
  `plan-strip-auth-scopes` reverted the Phase-7 `RefreshToken.scopes`
  mechanism, and `plan-auth-context` then dropped the unused token and
  system user entirely — the sandbox currently holds **no** credential.
  When the WS transport
  ([`../plans/plan-transport.md`](../plans/plan-transport.md) T4) ships
  the share-states subscription, the sandbox will authenticate to main
  for the first time and the credential is designed **fresh** then —
  scopes included; reuse [`auth-scoping-decision.md`](auth-scoping-decision.md)'s
  design (prefix-grant + exact-match grammar) as the starting point,
  this time with a real consumer forcing the shape.
- **`Context` group attribute for sandbox-originated actions.**
  `plan-auth-context` makes a genuinely sandbox-originated `Context`
  `user_id=None` (no user authored it). A richer audit answer would be a
  new optional `Context` field naming **which sandbox group** originated
  the action ("this came from the `custom` sandbox") — better for
  logbook/audit than a null user, without pretending a sandbox is a user.
  It needs a core `Context` change and is its own design; capture it when
  audit attribution actually needs it. **Do not** adopt the sandbox's
  `context_id` to carry this — that id is untrusted (see `_resolve_context`).
- **v1 removal. DONE (2026-05-28).** The numeric gate (Phase 11) was
  cleared by Phase 17; v1 was removed ahead of the "shipped a stable
  release" condition, relying on git history for rollback.
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
  `ALWAYS_MAIN` punt for the sandbox; a future spec on service-handler-level
  interception or sandbox-aware integration hooks. See the Phase 1
  spike doc.
- **Cross-sandbox in-process dependencies (ESPHome serial / BLE
  proxy).** Some integration pairs are coupled in-process — e.g. an
  ESPHome device exposing a serial proxy that another integration
  (ZHA, zwave_js, deCONZ, …) connects to. Today this only works if
  both integrations end up in the same sandbox group, because the
  setup-time coordination happens via Python calls/events the bridge
  doesn't forward. The classifier routes by built-in / custom / system,
  so a built-in ESPHome paired with a custom consumer would split
  across sandboxes and break. Fix shapes: (a) a "co-locate with X"
  classifier hint for known coupled pairs, or (b) extend the Phase 6
  event mirror beyond `<owned_domain>_*` to cover the coordination
  hooks. BLE proxy has the same shape. IR / RF (Broadlink-style) are
  simpler — one-way command flows with no setup-time enumeration —
  but still need dedicated cross-sandbox support to route the
  consumer's send-call to the producer. Worth a small spec before any
  cross-sandbox split actually trips this.

For per-failure remediation (residual `test-only` failures, the rare
`unknown` bucket entries, environmental rows) see
[`../BACKLOG.md`](../BACKLOG.md).
