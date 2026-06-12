# Review follow-up plans — index & execution order

> Source: the 2026-06-12 sandbox code review (7 finder angles + verification).
> These plans convert every verified finding into tasks. Execute **in order** —
> bug clusters first, then cleanup. Each plan is run via
> [`PLAN_RUNNER.md`](PLAN_RUNNER.md) (`phx:work`, fresh session per plan,
> orchestrator verifies + pushes).

## Docs: already landed (2026-06-12)

The documentation findings were fixed directly in the review session, not via a
plan: `OVERVIEW.md` was **deleted** (it duplicated `ARCHITECTURE.md` and was the
source of every doc-vs-doc disagreement; its code-map became `ARCHITECTURE.md`
§15), **v1 was scrubbed** from all live docs, `README.md` was rewritten,
`CLAUDE.md` was fixed (five core surfaces; OVERVIEW links re-pointed), and the
`ARCHITECTURE.md` drift (SETUP_RETRY, classify-at-entry-setup, 31-vs-32) was
corrected. The **one** remaining doc task — reconciling the §6/§10
security-posture wording — moved into **plan 2 (Phase 8)**, since it depends on
which gates that plan actually ships.

## Order

| # | Plan | Kind | Why this slot |
|---|---|---|---|
| 1 | [`plan-review-crash-recovery.md`](plan-review-crash-recovery.md) | bug (big) | Highest user impact: crash/restart/unload don't heal. Own plan. |
| 2 | [`plan-review-trust-boundary.md`](plan-review-trust-boundary.md) | security (big) | Main trusts the explicitly-untrusted sandbox; gaps vs §6/§10 claims. Closes with the security-doc reconciliation (Phase 8). Own plan. |
| 3 | [`plan-review-client-bridge-fixes.md`](plan-review-client-bridge-fixes.md) | bug (grouped) | Five smaller client-side races + the int→float wire fidelity bugs, grouped. |
| 4 | [`plan-review-flow-fidelity.md`](plan-review-flow-fidelity.md) | bug (grouped) | Config-flow forwarding correctness: version/options, menu/progress leak, discovery crash. |
| 5 | [`plan-review-simplification.md`](plan-review-simplification.md) | cleanup (own) | Dedup + dead code + boilerplate; do last so it rebases over the fixes. |

## Finding → plan coverage map (every verified finding has a home)

**Docs (landed):** README stale (ws/token/v1/RemoteStore/phase-17) ✅ · 31-vs-32 proxies ✅ · ARCHITECTURE SETUP_RETRY drift ✅ · classify-at-entry-setup drift ✅ · `SANDBOX_INCOMPATIBLE_PLATFORMS`/"JSON channel" ✅ · `test_phase4_subprocess` name ✅ · `entry_init` diagram label ✅ · v1 scrubbed everywhere ✅ · `OVERVIEW.md` deleted ✅ · security-posture wording ⏳ → plan 2 Phase 8.

**Crash recovery (plan 1):** restart doesn't tear down old bridge (`__init__.py:61`) · dead `sandbox_set_available` / stale state (`entity/__init__.py:158`) · `stop()` race hangs shutdown (`manager.py:200`) · respawn no ready-timeout (`manager.py:481`) · unload-while-down leaks platform (`router.py:174`) · `SETUP_RETRY` never scheduled (`router.py:134`) · `Channel.close()` no-op leaks transport (`channel.py:424`).

**Trust boundary (plan 2):** `fire_event` no main gate (`bridge.py:548`) · `register_service` no ownership check (`bridge.py:491`) · `register_entity` no group/entry-ownership check → device hijack (`bridge.py:386`) · translation cache poisoning (`translation.py:152`) · store server no quota/size cap (`bridge.py:687`) · context cache unbounded on resolve path (`bridge.py:378`) · unbounded inflight handler tasks / no read backpressure (`channel.py:540`) · security-doc reconciliation (Phase 8).

**Client + wire (plan 3):** services registered during `async_setup_entry` dropped (`service_mirror.py:83`) · `Ready` sent before handlers registered (`sandbox/__init__.py:194`) · state/removal lost while register in flight → ghost proxy (`entity_bridge.py:127`) · shutdown reply (restore_state) cancelled before flush (`sandbox/__init__.py:259`) · `ApprovedDomains` refcount leak (`entity_bridge.py:220`) · failed `entry_setup` leaves stale entry (`entry_runner.py:99`) · int→float via Struct for `entry.data`/`service_data` (`router.py:223`, `messages.py:72`) · store envelope version floats (`sandbox_bridge.py:76`).

**Flow (plan 4):** `version`/`minor_version`/`options` dropped on create_entry (`proxy_flow.py:197`) · MENU/EXTERNAL_STEP/SHOW_PROGRESS leak sandbox-side flow (`proxy_flow.py:248`) · discovery-sourced flows crash in `dict_to_struct` (`proxy_flow.py:121`).

**Simplification (plan 5):** channel/codec/messages mirror dedup + drift guard · domain-proxy `__init__` boilerplate collapse · dead `raise_not_proxied` + no-op block · `JsonCodec` default footgun · three drifted JSON coercers · task-per-state-change hot path.

## Cross-plan notes

- Plan 3's `entity_bridge.py` register-race fix and plan 5's "single writer
  task" refactor touch the same file — sequence plan 3 before plan 5 and let
  plan 5 rebase. Plan 5 explicitly defers the writer-task refactor if plan 3
  already restructured the push path.
- Plan 1's `Channel.close()` fix and plan 2's read-backpressure fix both edit
  `channel.py`; both are noted in each plan's Risks so the second to land
  rebases cleanly. (`channel.py` is a hand-mirrored file — see plan 5's drift
  guard; until that lands, **apply channel.py edits to BOTH mirrors**.)
