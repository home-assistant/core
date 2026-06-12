# Plan — Crash & restart recovery (review follow-up #2)

> Source: 2026-06-12 sandbox code review, lifecycle angle (all CONFIRMED).
> Status notes go to `sandbox/status/STATUS-plan-review-crash-recovery.md`.

## Goal

Make the documented "bounded crash recovery" (ARCHITECTURE §5) actually heal.
Today, after a sandbox crashes/respawns, the instance does **not** recover:
entities fail to re-register, stale state is served forever, and two paths can
hang HA shutdown. This plan fixes the restart/unload/teardown cluster as one
coherent unit because the bugs interlock (old-bridge teardown resolves two of
them at once).

## Success criteria

- [ ] After a sandbox crash + respawn, every entity re-registers and serves
      live state (no `"has already been setup!"` ValueError, no frozen ghosts).
- [ ] When the sandbox dies, its proxy entities go **unavailable** (not stale).
- [ ] HA shutdown never hangs on a sandbox (spawn-in-progress race + respawn
      ready-timeout both bounded).
- [ ] Unloading an entry while its sandbox is down still tears down the proxies
      + the `EntityComponent` platform registration.
- [ ] `Channel.close()` always closes the transport and awaits cancelled
      inflight tasks, even when EOF already set `_closed`.
- [ ] A `ChannelClosedError` during `entry_setup` results in an entry that
      actually retries (or a clearly-documented manual-reload contract).
- [ ] New regression tests cover crash→respawn→re-register, unload-while-down,
      and shutdown-during-spawn.
- [ ] `uv run pytest tests/components/sandbox/ --no-cov -q` +
      `uv run pytest sandbox/hass_client/ -q` green; `uv run prek run` clean.

## Phase 1 — Tear down the old bridge on restart (the keystone fix)

The root cause of the worst symptom: `_on_channel_ready` overwrites
`data.bridges`/`data.channels` with a fresh `SandboxBridge` but never destroys
the old one's proxy entities or its `EntityComponent._platforms[entry_id]`
registration. The first `register_entity` after respawn then raises
`ValueError("… has already been setup!")` (`entity_component.py:219`) and all
entities for the entry fail permanently.

- [ ] In `homeassistant/components/sandbox/__init__.py` (`_on_channel_ready`,
      `:61`): before installing the new bridge, if an old bridge exists for the
      group, call a new `SandboxBridge.async_teardown()` that:
      - removes every proxy entity it created from the state machine, and
      - unregisters each `EntityPlatform` from `EntityComponent._platforms`
        (the inverse of `async_register_remote_platform`).
- [ ] Add the inverse hook if one doesn't exist:
      `EntityComponent.async_unregister_remote_platform(entry_id)` in
      `homeassistant/helpers/entity_component.py` (mirror the Iron-Law "public
      hook, no private `_platforms` poke" rule the project already follows).
- [ ] Decide restart semantics: a respawn should re-drive `entry_setup` for the
      group's entries so the new bridge repopulates. Confirm the manager/router
      already does this on `ready`; if not, trigger it.

## Phase 2 — Mark proxies unavailable when the sandbox dies

`sandbox_set_available` (`entity/__init__.py:158`) has **zero callers** — nothing
flips proxies unavailable on channel close, so a dead sandbox's `light` stays
`on` to automations and UI.

- [ ] Add a channel-close / process-exit notification path. Options, pick one:
      (a) a `Channel` on-close callback the bridge subscribes to; or
      (b) the manager's `_supervise_until_exit`, after closing the channel,
      calls `bridge.async_mark_all_unavailable()`.
- [ ] `SandboxBridge.async_mark_all_unavailable()` iterates `_entities` and calls
      `sandbox_set_available(False)` on each (the method already exists and works
      — it's only the caller that's missing).
- [ ] On respawn + successful re-register, proxies return to available via the
      normal `state_changed`/register path — verify the round-trip flips back.

## Phase 3 — Bound the two shutdown/respawn hangs in `manager.py`

- [ ] **`stop()` spawn-in-progress race** (`manager.py:200`): `stop()` reads
      `self._process` (None mid-`_spawn`), skips `terminate()`, then awaits the
      supervisor forever while the freshly-spawned healthy child never exits.
      Fix: make `stop()` cancel the supervisor task (or set `_stopping` and have
      the supervisor check it *after* spawn returns and immediately terminate the
      new process), and/or bound the `await supervisor` with a timeout +
      SIGTERM/SIGKILL fallthrough.
- [ ] **Respawn has no ready-timeout** (`manager.py:481`): `ready_timeout` is
      only applied in the first `start()`. In `_supervise_until_exit`, wrap the
      `asyncio.wait({ready_task, exit_task})` with the same `ready_timeout`; on
      timeout, treat as a failed attempt (count against the restart budget) and
      kill the hung child, instead of leaving state `starting` forever.
- [ ] Confirm `ensure_started` no longer hands back a `starting` zombie whose
      channel is live-but-unanswered (`manager.py:597`); if a respawn is still
      mid-flight, callers should await readiness or get `SandboxFailedError`.

## Phase 4 — Don't leak the platform on unload-while-down

`router.async_unload_entry` (`router.py:174`) returns `True` without calling
`bridge.async_unload_entry` when `channel is None`, leaking the proxies and the
`EntityComponent._platforms[entry_id]` registration → re-setup hits the same
`"has already been setup!"`.

- [ ] When the sandbox/channel is down, still run the **main-side** cleanup
      (`bridge.async_unload_entry` or the Phase 1 `async_teardown` scoped to the
      entry) before returning `True`. The remote `entry_unload` RPC can be
      skipped (the process is gone), but the proxies/platform must be removed.
- [ ] Share the teardown helper with Phase 1 so there's one code path that
      removes proxies + unregisters the platform.

## Phase 5 — Fix `Channel.close()` no-op + the SETUP_RETRY non-retry

- [ ] **`Channel.close()` early-return** (`channel.py:424`): the EOF `finally`
      sets `_closed=True` and cancels (never awaits) inflight tasks; `close()`
      then returns at `if self._closed: return`, so `transport.close()` and the
      inflight `gather` never run → stdin pipe / unix conn leaks each cycle.
      Fix: split "already closed" (idempotent re-entry) from "work not yet done"
      — always ensure the transport is closed and cancelled inflight tasks are
      awaited exactly once, regardless of who set `_closed`. **Apply to BOTH
      channel.py mirrors** (main + client) until the simplification plan's drift guard lands.
- [ ] **`SETUP_RETRY` never scheduled** (`router.py:134`): the router sets
      `SETUP_RETRY` directly, bypassing `ConfigEntry.async_setup` where the retry
      timer lives, so the entry wedges and a later `async_setup` raises
      `OperationNotAllowed`. Fix: route the channel-closed case through a path
      that actually schedules a retry (e.g. raise `ConfigEntryNotReady`-equivalent
      so core's machinery schedules `async_call_later`, or explicitly schedule a
      reload). If a true retry isn't feasible from the router, fall back to
      `SETUP_ERROR` (honest "needs manual reload") rather than a wedged
      `SETUP_RETRY` — and update `ARCHITECTURE.md` §5 accordingly.

## Phase 6 — Regression tests

- [ ] Crash→respawn→re-register: spawn (in-process plugin), register an entity,
      drop the channel, respawn, re-send `register_entity`; assert the entity is
      live (no ValueError, state updates flow). Guards Phase 1.
- [ ] Sandbox-dies-availability: register entity `on`, kill channel, assert proxy
      `available is False`; respawn, assert it recovers. Guards Phase 2.
- [ ] Shutdown-during-spawn: trigger `stop()` while a spawn is in flight; assert
      it completes within the grace window (no hang). Guards Phase 3.
- [ ] Unload-while-down: set up entry, drop sandbox, unload entry, respawn +
      re-setup; assert entities register (no leaked platform). Guards Phase 4.
- [ ] `Channel.close()` after EOF closes the transport (assert transport closed,
      inflight tasks awaited). Guards Phase 5.

## Verification

```bash
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
bash sandbox/proto/check_drift.sh   # if channel.py touched proto-adjacent consts
uv run prek run --files <changed>
```

## Risks / open questions

1. **`channel.py` is hand-mirrored** (main + client). Until the simplification plan adds a drift
   guard, every `channel.py` edit here MUST be applied to both copies — the
   Phase 5 fix especially. Note it in the commit.
2. **Re-drive `entry_setup` on respawn** (Phase 1): confirm whether the manager
   already re-sends entry setup on `ready`, or whether the router must. Don't
   double-setup (idempotency: `entry_runner` rejects an already-loaded entry —
   see the client-bridge-fixes plan's stale-entry fix, which interacts here).
3. **SETUP_RETRY true retry vs honest error** (Phase 5): if core's retry
   scheduler genuinely can't be reached from the router seam, shipping
   `SETUP_ERROR` + doc fix is acceptable for this iteration; flag a follow-up.
4. **The trust-boundary plan also edits `channel.py`** (read backpressure). Whichever lands second
   rebases; keep the two changes in separate commits.

## Out of scope

- Active health-ping loop (ARCHITECTURE notes it as future) — process-exit
  detection stays the liveness signal; this plan only fixes the *recovery* once
  exit is detected.
- The unbounded-inflight-tasks DoS (`channel.py:540`) — that's the trust-boundary plan.
