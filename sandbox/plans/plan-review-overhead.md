# Plan — Overhead & simplification (review follow-up, 2026-07-07)

> Source: 2026-07-07 performance/simplification review of the sandbox client +
> core hooks (4 review angles + measurements on real code; benchmarks run in
> this repo's venvs, protobuf 6.32.0 upb, Python 3.14). Findings marked
> **[measured]** have numbers from this review; the benchmark scripts are
> reproducible from the descriptions.
>
> Baseline at review time: `1c9285cec8a`, both suites green
> (245 core-side + 111 client-side).

## Measured baseline — where the overhead actually is

| Metric | Value |
|---|---|
| Empty sandbox subprocess, spawn → Ready | **~930 ms** |
| Empty sandbox subprocess RSS | **~117 MB** |
| — of which: importing `homeassistant.core` + `config_entries` | ~215 ms, 74 MB |
| — of which: `HomeAssistant()` ctor (lazy-imports `core_config` → `zone` → `websocket_api` → `http`/aiohttp) | ~180 ms, +31 MB |
| Cross-process ping RTT (stdio pipes) | p50 36 µs, p99 91 µs |
| Channel push throughput (prebuilt msgs, socketpair) | ~92 k msg/s (10.9 µs/msg) |
| Channel push incl. Struct build | ~55 k msg/s (18.2 µs/msg) |
| Pipelined call throughput | ~54 k calls/s |
| One state_changed serialize round-trip, production Struct path | **26.3 µs** (11.6 µs `Struct.update` + 9.5 µs `struct_to_dict` + 1.3 µs encode + 2.1 µs decode) |
| Same payload as orjson-bytes-in-proto | **2.1 µs** (~13× faster, and ~30% smaller on the wire) |
| First `register_entity` on main: eager import of all 31 domain proxy modules | **~384 ms, +67 MB RSS**, on the event loop (cold-import worst case; warm installs pay less) |

Headline: the channel/dispatch core is fine. The avoidable overhead is
(1) `google.protobuf.Struct` for every dynamic payload, (2) task-per-frame ×2
per state change, (3) the eager 31-domain import on main, and (4) the sandbox
boot importing main-HA's HTTP stack it never uses. Everything below is
ordered: correctness bugs found along the way first (they gate the perf work),
then perf, then simplification.

**But read §E first**: two critical findings (private-hass registries never
load, so real platforms can't add entities; and the compat lane never actually
engages the sandbox) mean the end-to-end entity path is broken for real
integrations today and the number that claims otherwise is measuring a no-op.

## A. Correctness bugs found during the review (fix before/with the perf work)

### A1. `_push_state` crashes on datetime attributes — entity goes permanently stale — HIGH
`hass_client/entity_bridge.py:311` (and `:244` for initial attributes) feeds
raw `new_state.attributes` into `Struct.update`, which **[measured]** raises
`ValueError: Unexpected type` for `datetime` (also `date`, `Decimal`, sets,
enums). Common HA attributes (`sun.next_dawn`-style timestamps,
`last_triggered`) crash inside a fire-and-forget task, *outside* the `try`
that wraps only the push — the entity registers, then never updates on main.
`_describe_entity` runs `json_safe` on capabilities and `event_mirror` runs it
on event data; the hottest path is the one place with no coercion. Fixed
structurally by B1; standalone fix is `json_safe` here too.

### A2. `ConfigEntries.async_unload` marks `NOT_LOADED` when the router returns `False` — HIGH
`homeassistant/config_entries.py:2469-2474`: `if result is not None:` sets
`NOT_LOADED` and returns — including `result is False`, which the sandbox
router deliberately returns when a live sandbox *refused* the unload
(`router.py` ChannelRemoteError path, proxies intentionally left in place).
Core's state machine then says unloaded while the remote entry + proxies are
live; the next setup races "already setup". Fix: only set `NOT_LOADED` when
`result` is truthy — or better, A5.

### A3. Mirrored services survive bridge teardown bound to a dead channel — HIGH
`bridge.py`: `_mirrored_services` is only ever removed via
`_handle_unregister_service` (needs a live sandbox). `async_teardown` /
`_async_teardown_entry` never sweep it. After a crash/respawn the stale
forwarder (closure over the dead bridge) stays on `hass.services`; the new
bridge's `has_service()` check sees the slot and skips reinstall — every call
to that service raises "channel closed" until HA restarts. No test covers it.
Fix: sweep `_mirrored_services` with `hass.services.async_remove` in
`async_teardown`, clear the set.

### A4. Router setup/unload run outside `entry.setup_lock` — MEDIUM
`config_entries.py:2432, 2468`: the router branches ignore the `_lock`
parameter, so a direct `async_setup(entry_id)` (user retry, discovery) can run
two `entry_setup` RPCs concurrently for one entry. Wrap the router calls in
`async with entry.setup_lock` when `_lock` is true, mirroring the default
path.

### A5. Setup/unload state ownership is asymmetric (design; subsumes A2) — MEDIUM
On setup the *router* pokes `entry._async_set_state` six times (`# noqa:
SLF001` from a component); on unload *core* sets the state. Pick one owner —
cleanest for upstreaming is core owning both, with the router protocol
returning success/failure(+reason) and core mapping it (it already knows how,
via `ConfigEntryError`). Removes every SLF001 from `router.py` and fixes A2
structurally.

### A6. Translation overlay clobbers the title fallback — MEDIUM (and a simplification)
`helpers/translation.py`: `_async_get_component_strings` fills
`component_translations["title"]` from the sandbox catalog (lines 135-152),
then `_async_overlay_sandbox_strings` runs *after* it in `_async_load` and
`update(by_domain)` **replaces** the whole per-domain dict. The sandbox-side
handler pre-fills `title` from `integration.name`, so the common case works —
but any provider response without `title` (degraded/partial) wipes the
fallback. Fix + diff shrink: run the overlay *inside*
`_async_get_component_strings` before the title-fallback loop, delete
`_async_overlay_sandbox_strings`, and `_TranslationCache._async_load` goes
back to dev-identical.

### A7. Upsert doesn't clear dropped `device_class`/`device_info` — LOW
`entity/__init__.py:123-124`: `sandbox_update_description` clears
name/icon/category when absent but only *sets* device_class when truthy.
Fold init + upsert into one `_apply_description` helper with symmetric
clearing (see C3).

### A8. Oversize write poisons the whole channel — MEDIUM
`channel.py` (both mirrors): `MAX_FRAME_SIZE` is enforced on read only. One
oversized outbound payload (giant store save / translations / BrowseMedia
tree) is written happily; the *peer* aborts the channel → full sandbox restart
with every pending call failed. Check `len(data)` in `Channel._write` and fail
just that call.

## B. Overhead reduction (the perf plan)

### B1. Replace every `google.protobuf.Struct`/`ListValue` field with orjson bytes — HIGH [measured]
The single biggest win, and it deletes code + a bug class:

- **13× on the state-changed hot path** (26.3 µs → 2.1 µs serialize
  round-trip): `Struct.update` is 11.6 µs vs 0.2 µs for `orjson.dumps`;
  `struct_to_dict` is a 9.5 µs pure-Python recursive walk vs 0.5 µs
  `orjson.loads`. Wire ~30% smaller.
- **The store path is worse today**: `prepare_save_json` (orjson bytes) →
  stdlib `json.loads` → `dict_to_struct` → proto → wire → proto →
  `struct_to_dict` → dict → main's Store re-serializes with orjson to disk.
  Four tree conversions + two JSON encodes per save become: orjson bytes →
  wire → disk-ish.
- **Kills the number-fidelity hacks**: Struct stores all numbers as double, so
  `_value_to_py` "restore whole floats to int" corrupts genuine floats
  (`2.0` → `2`) and ints > 2^53 silently lose precision **[measured:
  `2**53+1` round-trips wrong]**. The whole "Numbers note" in `messages.py`
  and the plan-3 int-restoration work exist to patch a problem the wire format
  self-inflicts. JSON bytes preserve int/float natively.
- **Fixes A1 by construction**: one `json_safe`+orjson coercer, always
  applied, replaces the "some paths coerce, some don't" spread. Also fixes the
  main-side gap (`bridge.py` `_raw_call_service`/`async_entity_query` feed
  `service_data` into `dict_to_struct` uncoerced — `cv.datetime` service data
  crashes today).
- Deletes `struct_to_dict` / `dict_to_struct` / `_value_to_py` /
  `list_to_listvalue` (~45 lines × 2 mirrors).

Change shape: in `sandbox.proto`, `google.protobuf.Struct foo` →
`bytes foo_json`; producer does `orjson.dumps(json_safe(value))`, consumer
`orjson.loads`. Keep every typed scalar field (ids, version, context_id,
supported_features) exactly as-is — that's where proto's typing pays; the
Struct blobs were never typed anyway.

### B2. Inline push dispatch + per-entity coalescing (revives deferred plan-5 Phase 6) — MEDIUM [measured]
Every state change spawns **two** asyncio tasks (sandbox `_on_state_changed`
create_task + main `_dispatch` `_spawn_handler`) plus a semaphore acquire —
yet `_handle_state_changed` contains zero awaits (pure dict work +
`async_write_ha_state`). Per-entity ordering currently survives only because
task start order happens to be FIFO — an accidental invariant.

- Main side: add an inline-dispatch registration for push handlers
  (`register(type, handler, inline=True)`) executing in the read loop; keep
  task dispatch for calls. Removes a task+semaphore per push and makes
  ordering guaranteed.
- Sandbox side: the promised single-writer queue — per-entity latest-state
  slot + one writer task. This also subsumes the `_removed_while_pending` /
  post-register flush machinery (entity_bridge.py:184-209), **and** fixes the
  overload story: today `channel.py` sheds pushes silently over
  `DEFAULT_MAX_QUEUED`, so the *last* state update in a burst can be dropped,
  leaving a proxy stale forever. Last-write-wins data should coalesce (one
  slot per entity, nothing to shed), not drop. At minimum, log the drop —
  today it's a bare `return`.

Channel dispatch itself is healthy: 92 k msg/s / 54 k calls/s measured — no
transport work needed beyond the trivia in D.

### B3. Make the domain-proxy registry actually lazy — MEDIUM [measured]
`entity/__init__.py:303` runs `_build_registry()` at module import, and the
module is first imported inside the `register_entity` RPC handler — so the
first sandboxed entity **blocks main's event loop importing all 31 domain
component packages: ~384 ms / +67 MB cold** (warm installs pay whatever isn't
already imported). The docstring says "lazy-build … to avoid the import
storm"; the code defeats it. Every entry follows `<domain>.py` /
`Sandbox<Camel>Entity`, so replace the table with memoized
`importlib.import_module(f".{domain}", __package__)` + `getattr` in
`build_proxy`, falling back to `SandboxProxyEntity`. Deletes ~75 lines and
imports only the domains actually used.

### B4. Slim the sandbox boot — MEDIUM [measured]
~930 ms / 117 MB per (empty) group. Attribution: 74 MB / ~215 ms is importing
`homeassistant.core` + `config_entries` (unavoidable for a private HA);
**+31 MB / ~180 ms is `HomeAssistant()`'s ctor lazy-importing `core_config` →
`components.zone` → `helpers.collection` → `websocket_api` → `http`** — the
whole aiohttp/HTTP stack in a subprocess that never serves HTTP. Options, in
increasing effort: (a) accept it (2 default groups ≈ 235 MB; lazy spawn
already avoids paying it when unused); (b) pre-import in a forkserver-style
template process if group count grows; (c) upstream: make `core_config`'s
zone import lazy (it's for zone validation) — benefits all of HA's test
suite too, not just the sandbox. Not urgent at 2-3 groups; document the
per-group cost in ARCHITECTURE §5 either way.

### B5. Hot-path micro-cleanups — LOW
- `entity/__init__.py:147` `sandbox_apply_state` re-copies the dict
  `struct_to_dict` just built exclusively for it (`bridge.py:577`); take
  ownership. (Moot if B1 lands — then it owns the `orjson.loads` result.)
- `bridge.py:679-702` `_owned_domains()` rebuilds three sets over **all**
  config entries on **every** `fire_event`. Cache on the bridge with a dirty
  flag (invalidate on proxy/platform/entry changes).
- `entity/climate.py:45` imports `UnitOfTemperature` inside the
  `temperature_unit` property (read per state write); import at module top
  like `water_heater.py`.
- `channel.py:245` `write_frame` concatenates header+body (full-frame copy per
  write, MB-scale for store/translation frames): two `write()` calls before
  one `drain()`.
- `sandbox_bridge.py:76` uses stdlib `json.loads` on orjson-produced bytes
  (moot with B1).

## C. Simplification

### C1. Fold `protocol.py` into `messages.py` — the real drift hole — MEDIUM
`check_mirror_drift.sh` guards `channel.py codec_protobuf.py messages.py` —
**not** `protocol.py`, which is hand-mirrored with deliberately different
docstrings (undiffable) and is *incomplete*: `sandbox/ping` and the three
`flow_*` types have no `MSG_` constants and appear as string literals in ≥6
files. Every constant it defines already exists as a guarded `REGISTRY` key.
Move the `MSG_*` names into `messages.py`, add the four missing ones, replace
the literals, shrink/delete `protocol.py`. Also add the `_pb2` gencode to the
every-commit mirror diff (today only the manual `check_drift.sh` lane catches
a hand-edit).

### C2. Mirror-vs-package verdict: keep the mirror for now — deliberate
A published wire wheel would satisfy both constraints (HA imports PyPI deps
via manifest requirements; `hass_client` stays standalone), but costs a
publish-bump-sync dance per wire change while the proto is still moving.
Keep the mirror + drift guard; close the C1 hole; treat first external/HACS
consumption of the protocol as the trigger to cut the wheel.

### C3. bridge.py (1153 lines) split seams + dedup — LOW-MEDIUM
Mechanical, land opportunistically: store server (~150 lines) → `store.py`;
service-forwarder helpers (~100 lines) → its own module (also removes the
`# noqa: SLF001` pokes by making the seam explicit); `SandboxEntityDescription`
+ device-info deserialise → `description.py` (dissolves the bridge↔entity
import cycle forcing the lazy proxy import). Plus: one `_apply_description`
shared by proxy `__init__` and `sandbox_update_description` (fixes A7).

### C4. Entity proxies: do NOT table-drive them — deliberate
Quantified: 152 properties + 110 forwarders across 2 303 lines; ~60%
mechanical. A metaclass/table approach was evaluated and rejected: method
signatures are load-bearing (domain components call proxies with specific
kwargs; `filter_turn_on_params` etc.), and generated members lose
mypy-vs-domain-contract checking — exactly where the value is. The cheap
middle (a `state_attr(key, coerce)` property helper, ~500 lines saved) is
optional; the current code is write-once and trivially reviewable.

### C5. Dead code / speculative surface — LOW
- `config_entries.py`: `sandbox` in `UPDATE_ENTRY_CONFIG_ENTRY_ATTRS` +
  the `async_update_entry(sandbox=...)` plumbing is never called (verified;
  only `ConfigFlowResult` + storage set it). Move `"sandbox"` to
  `FROZEN_CONFIG_ENTRY_ATTRS`; stronger immutability, ~8 lines less core diff.
- `bridge.py`: `SandboxEntityDescription.device_id` is write-only; delete.
  `_parse_supports_response` has two unreachable branches (input is always a
  proto3 str); collapse. `_translate_remote_error` has duplicate branches;
  merge.
- `__init__.py`: `SandboxData.channels` has no production reader (tests only)
  — drop or annotate.
- `channel.py`: `drain_inflight`'s `is not self._reader_task` filter is dead
  (reader is never in `_inflight`); `from_transport` duplicates `__init__`
  (and silently drops `max_queued`); `_next_id` should wrap at uint32 for a
  months-lived channel; `codec_protobuf._serialize_body`'s None branch is
  `b""` either way.
- `entity_bridge.py` + `bridge.py`: `getattr(x, "attr", None)` on dataclasses
  that always have the field — use plain access per repo guidance.

## D. Core-hooks overhead audit (upstreamability) — CLEAN

Verified for the five core surfaces: **zero added cost on non-sandbox
installs** on every hot path. Translation overlay + catalog run only on
cache-miss loads and bail on the first `hass.data.get` when no provider is
registered; cached lookups are byte-identical to dev. `Store` pays one
C-level `ContextVar.get()` per load/write/remove (~tens of ns on an IO path)
— the only unconditional cost, and inherent to the design. Router checks are
`is not None` on rare operations. `ConfigEntry.sandbox` doesn't change the
storage shape when unset. The hooks are upstream-shaped; A2/A4/A5/A6 are the
items to fix before proposing them.

## E. Client runtime (sandbox side)

### E1. The private hass never loads its registries — real platforms cannot add entities — CRITICAL
`FlowRunner.create` builds a bare `HomeAssistant` and never runs bootstrap's
`async_load_base_functionality` — the only caller of the registry
`async_load`s. `er.async_get(hass)` lazily constructs an `EntityRegistry`
whose `.entities` is only assigned inside `async_load`
(entity_registry.py:2143-2145). **Empirically reproduced** (real `sun`
integration on a `FlowRunner.create`-style hass): every `_async_add_entity`
dies with `AttributeError: 'EntityRegistry' object has no attribute
'entities'` while `config_entries.async_setup` still reports `ok=True` — the
sandbox ACKs `entry_setup` and silently bridges **zero entities**. No test
catches it because every entity-bridge test injects fakes into
`component._entities` and fires `EVENT_STATE_CHANGED` by hand. The comment at
`sandbox/__init__.py:166-172` claiming the registries "already ran their
async_load inside FlowRunner.create" is false. Fix: gather the
area/category/device/entity/floor/issue/label registry `async_load`s in
`FlowRunner.create` (before the channel/contextvar, keeping the documented
local-tempdir routing), plus one client test that drives a real platform
through `EntryRunner`.

### E2. The compat lane never routes anything through a sandbox — CRITICAL
Both pytest plugins install only the autotag in `pytest_configure`; the
`sandbox_inprocess` / subprocess fixtures are **opt-in** and no vanilla
integration test requests them (verified: plain fixture, zero usages outside
the sandbox's own tests). So `run_compat.py`'s 7 646-test / 99.97% sweep runs
vanilla tests where `hass.config_entries.router is None` and the tagged entry
sets up locally — **COMPAT.md measures the tag's inertness, not sandbox
compatibility**, and explains why E1 never surfaced. Fix: an autouse fixture
in the plugins that sets up the in-process (resp. subprocess) sandbox before
each test, and make `run_compat.py` assert the router actually engaged (count
`sandbox/entry_setup` frames) so the lane can't silently regress to a no-op.
E1 + E2 are each the test that would have caught the other — land together.

### E3. Main's core config never reaches the private hass — MEDIUM
Nothing on `EntrySetup` (or elsewhere) carries time zone / lat-long / unit
system / language; sandboxed integrations computing sun times, distances, or
unit conversions run against HA defaults. Add a wire field on `entry_setup`
or a one-time `sandbox/core_config` push.

### E4. Runtime teardown never stops the private hass — MEDIUM (test lane)
`run()`'s finally tears down mirrors/bridge/channel but never
`hass.async_stop()` — the ctor-created executor + all `hass.data` leak per
in-process sandbox; prod is saved by process exit. `InProcessSandbox.stop`
also skips `_run_graceful_shutdown` (no unload, no FINAL_WRITE), so pending
`async_delay_save` timers linger on the shared test loop. Fix both in the
runtime finally / fixture stop path. Related structure nit: `FlowRunner` owns
the hass factory and its `async_stop` doubles as whole-hass teardown while
every sibling takes `hass` — move construction into `SandboxRuntime`.

### E5. Client-side hot path (feeds B2) — MEDIUM
Confirmed by the client review, same as B2's sandbox half: task per state
change, no steady-state coalescing (registered entities do get the slim
`state_changed` — good — and the `_last_hash` resend guard works). Extras:
an entity that fails `_describe` (no owning entry) re-attempts a full
register on **every** state write forever — add a sticky `_skipped` set;
`_last_hash` leaks on the normal unregister path (only the racy-removal path
pops it).

### E6. Client simplification / small items — LOW
- `flow_runner._to_json_safe` duplicates `_json.json_safe` — the exact drift
  `_json.py`'s docstring says it exists to end; replace + delete.
- `ApprovedDomains` refcounting **verified correct — keep** (entry-level and
  per-entity contributors release independently; a set would un-approve
  domains still in use).
- `sources.py`: the global `_CACHE_LOCK` serializes downloads of *different*
  repos (per-key task memoization would parallelize); `_TARBALL_CACHE` pins
  whole tarball bytes for process lifetime — keep a fetched-key set instead.
- Autotag install/uninstall duplicated verbatim between the two plugins —
  fold into `_autotag.py`.
- `event_mirror.py` docstring describes an `event_filter=` fast path that
  isn't passed — fix code or comment.
- `service_mirror`: two `async_services_for_domain` lookups per registration
  — merge (cosmetic).

## Discovered during execution (open, not in the original findings)

- **Timestamp sensor proxies break on state fidelity**: a sandboxed sensor
  with `device_class: timestamp` pushes its state as a string, but
  `SensorEntity.state` requires a `datetime` (`AttributeError: 'str' object
  has no attribute 'tzinfo'` kills the proxy's entity add). Blocks several
  sun compat tests even after core-config mirroring (E3). Fix shape: the
  sensor proxy should rebuild `native_value` typed from the pushed state
  for timestamp/date device classes.
- The compat lane (now real, E2) reports 8 failing sun tests — the honest
  baseline replacing the no-op 99.97%. Failure notes: listener-count
  assertions see the proxy architecture; unload/remove semantics; recorder
  attribute exclusion; the timestamp issue above.

## Suggested execution order

1. **E1 + E2 as one plan** — the sandbox currently cannot bridge a real
   integration's entities, and the lane that should prove it is a no-op.
   Everything else is tuning a path these two must first make real.
2. **A-cluster bug fixes** (A1 standalone only if B1 doesn't land immediately;
   A2+A4(+A5), A3, A6, A8, E4) — small, test-backed, independent.
3. **B1 Struct→orjson-bytes** — biggest perf win, deletes the most code,
   subsumes A1 and half of B5; touches proto + both mirrors + every call
   site, so do it as its own plan with the drift guard green throughout.
4. **B2/E5 inline push + single-writer queue** — revives plan-5 Phase 6 with
   the measurements that justify it.
5. **B3 lazy proxy registry** — small and self-contained.
6. **C1 protocol.py fold** + C5/E6 dead code — cleanup pass.
7. B4/C3/E3 as opportunity allows.
