# Compat failure clustering — findings (2026-07-08)

The first honest full-tree compat baseline (all 1148 integration suites through
the real in-process sandbox lane), its failure clustering, and the fixes that
followed.

## Files in this directory

- `COMPAT.csv` / `COMPAT_LATEST.md` — the **baseline** sweep at commit
  `9c0d69d8f3f` (router-bypass fix, before the reauth work).
- `COMPAT-postfix.csv` / `COMPAT-postfix.md` — a re-sweep after the
  reauth/reconfigure entry-carry fix (`402e7987bd5`).
- `clusters/clusters.md` + `clusters.json` — failure clustering over the
  post-fix `--tb=line` error dumps (regenerate with
  `python sandbox/cluster_failures.py sandbox/reports/2026-07-08/clusters`).

## The number

`run_compat.py` buckets each suite: **pass** (sandboxed, all green), **main**
(classifier routes to main — camera/tts/system/`ALWAYS_MAIN`, vanilla behavior
is correct), **issues** (sandboxed, some fail), **no_op** (tagged but nothing
routed — platform-base suites driving mock entities), **timeout**.

Test-level across the 763 suites that actually engaged a sandbox:

| | passed | failed | errors | pass-rate |
|---|---:|---:|---:|---:|
| Baseline (`9c0d69d8f3f`) | 29,713 | 15,625 | 3,752 | 60.5 % |
| After reauth fix (`402e7987bd5`) | 30,067 | 15,272 | 2,865 | **62.4 %** |

The reauth/reconfigure fix added ~354 passes and removed ~887 errors (the
`UnknownEntry` hard-errors became runnable flows). No suite flipped fully green
because each affected suite has *other* failing tests too — the number moves in
aggregate, not in whole suites, until several clusters are cleared together.

Either way this replaces the old 99.97 %, which measured a lane that never
routed anything.

## Failure clusters (post-fix), by leverage

Counts are `<failures> / <integrations>` from `clusters/clusters.md`. The
`issues` failures collapse into a handful of cross-cutting root causes.

### 1. Config-flow terminal actions don't cross back to main — ~1,040 / 172 (+ the `sandbox_flow_error` sub-clusters)

`assert <ABORT> is <FORM>`, plus `'sandbox_flow_error' == 'already_configured'`
(164/105) and `== 'no_devices_found'` (97/49). Three related mechanisms, all
"the flow ran in the sandbox but its effect on main-owned state was lost":

- **reauth/reconfigure writeback (residual of the fix).** The entry-carry fix
  (`402e7987bd5`) lets these flows *run*; the terminal
  `async_update_reload_and_abort(entry, data_updates=...)` still mutates the
  sandbox's private entry copy, so main's entry keeps its old data and
  `entry.data == <new>` assertions fail. **Fix:** the reauth/reconfigure abort
  `FlowResult` carries the entry mutations (data/options/unique_id/title) back
  to main, and main applies them + reloads — the mirror of how `CREATE_ENTRY`
  already crosses.
- **Duplicate detection can't see main's entries.** `async_set_unique_id()` +
  `_abort_if_unique_id_configured()` / `_async_current_entries()` check the
  *sandbox's* private `config_entries`, which is empty (main owns entries). A
  flow that should abort `already_configured` doesn't. **Fix:** seed the
  sandbox flow with main's existing entries for the handler's domain (their
  identity fields — the same carry as the reauth entry, for the whole domain),
  or answer the unique-id check over the channel.
- **Input marshalling drops keys.** Some flows raise `KeyError` on a step
  (e.g. `adguard` step user: `'verify_ssl'`) — a form field with a schema
  default isn't present in the round-tripped `user_input`, so the sandbox
  flow's `user_input["verify_ssl"]` raises and the proxy aborts
  `sandbox_flow_error`. **Fix:** apply the data-schema defaults before
  forwarding user_input, or preserve keys the sandbox schema declares.

### 2. `SETUP_ERROR` where the integration means `SETUP_RETRY` — ~788 / 333

The broadest cluster by integration count. A sandboxed integration raising
`ConfigEntryNotReady` (device offline → retry) surfaces as `SETUP_ERROR`.
Previously unreachable because the router ran outside `ConfigEntry.async_setup`;
now that the consult lives *inside* it (`9c0d69d8f3f`), a router-driven retry
is reachable. **Fix:** the sandbox reports `ConfigEntryNotReady` distinctly on
`EntrySetupResult` (a flag, not a generic failure), and the entry-level consult
re-raises it so core arms its own `SETUP_RETRY` timer exactly as for a local
integration. High leverage — 333 integrations touch this.

### 3. Setup fails outright — `SETUP_ERROR` is `LOADED` — ~809 / 85

The integration's `async_setup_entry` raises in the sandbox where it wouldn't
locally. Heterogeneous: coordinator first-refresh differences, a dependency the
sandbox boot doesn't provide, or the same missing-`runtime_data`/marshalling
issues surfacing at setup. Needs per-integration reads of the error dumps;
some overlap with clusters 2 and 8.

### 4. `ServiceNotFound: Action <x> not found` — ~662 / 61

A test calls a service the integration registered during setup before the
`ServiceMirror` mirrored it, or the service falls outside the approved-domain
gate. The settle shim covers the common timing case; the residual is worth
checking against `ServiceMirror`'s registered-during-setup replay and the
gate's domain set.

### 5. Entity missing on main — `NoneType has no attribute 'state' / 'attributes'` — ~519 / 87 + 144 / 27

`hass.states.get(...)` is `None` where a bridged entity is expected.
Sub-causes: coordinator/late-added entities outside the settle window, and
helper-domain entities the integration creates outside its own config-entry
platform (which `entity_bridge._describe` skips — the sole-domain-entry
attribution added this session covers own-domain entities but not helpers).

### 6. Snapshot drift — ~822 / 218

`assert [+ received] == [- snapshot]`. Syrupy `.ambr` captures the proxy shape +
the `sandbox` field a routed entry now carries (`+ 'sandbox': 'built-in'`) +
`created_at` drift. Mostly a test-side refresh (`--snapshot-update` per
integration) — but triage first: a subset are genuine shape diffs (proxy
`unique_id` namespacing `<domain>:<id>`, dropped attributes).

### 7. Sandbox abort reasons have no handler translation — part of "Regex did not match" ~377 / 71

`Translation not found for <domain>: config.abort.sandbox_flow_error`. When the
proxy aborts with an internal reason (`sandbox_flow_error`, `sandbox_unavailable`,
`sandbox_flow_terminated`), the frontend/test validates it against the *handler's*
`strings.json`, which will never contain a sandbox-internal key. **Fix:** ship
these abort reasons in the `sandbox` integration's own `strings.json` and have
the flow-result validator fall back to the sandbox translations for
sandbox-owned reasons — or, better, surface the real remote abort reason
instead of a generic one wherever the sandbox flow actually aborted (vs raised).

### 8. `'MockConfigEntry' object has no attribute 'runtime_data'` — ~332 / 50 — **inherent, not a bug**

The integration sets `entry.runtime_data = <coordinator>` inside its
`async_setup_entry` — which runs in the sandbox, on the sandbox's entry copy.
`runtime_data` is a live Python object (a coordinator, a client session); it
**cannot** cross to main by design. Tests that read `entry.runtime_data` are
white-box tests reaching into runtime state that lives in the sandbox — the
same class as tests that patch the integration's client library on main. Not
fixable without exposing sandbox internals; count these as expected
white-box divergences, not compat gaps.

## Suggested order to drive the number up

1. **Config-flow writeback + entry visibility** (cluster 1) — carry
   reauth/reconfigure entry mutations back to main, seed main's existing
   entries for duplicate detection, apply schema defaults to forwarded input.
   Biggest flow cluster; builds directly on the entry-carry fix.
2. **Router-driven `SETUP_RETRY`** (cluster 2) — now reachable; 333
   integrations.
3. **Sandbox abort-reason translations** (cluster 7) — small, mechanical,
   clears a whole validation-error family.
4. **Snapshot triage + refresh** (cluster 6) — separate genuine diffs from the
   expected `sandbox`-field drift, then mass-update the rest.
5. Clusters 3/4/5 are heterogeneous — per-integration reads.
   Cluster 8 is inherent — exclude from the target.

Clusters 1, 2, 6 alone cover the large majority of failing tests.

## Caveats on the method

The clustering signatures come from `--tb=line` (one frame + exception +
message per failure). That attributes each failure to the *raising* frame, which
for an assertion is the test file (`tests/<suite>`) — good for grouping by
symptom, less so for grouping by mechanism. Where a cluster's mechanism
mattered, it was confirmed by reading the full dumps in `$SANDBOX_ERRORS_DIR`
(`/tmp/sandbox_errors/<integration>.txt`), not from the signature alone.
