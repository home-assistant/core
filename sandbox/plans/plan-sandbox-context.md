# Plan: `current_sandbox` ContextVar — replace store patching, enable cross-sandbox calls

> **Execute first.** This plan replaces the module-level monkey-patch of
> `homeassistant.helpers.storage.Store` (today's `install_remote_store`) with
> a `ContextVar`-based routing primitive in **core HA**. The same primitive
> covers the cross-sandbox in-process dependencies the CLAUDE.md follow-ups
> flag (infrared, radio frequency; eventually BLE / ESPHome serial).

## Decisions (locked 2026-06-03)

- **Q1 — IR / RF call surface: DEFERRED.** This plan ships only the
  contextvar primitive (Phase A). Cross-sandbox IR/RF (and BLE / serial)
  open as new plans when an actual consumer lands and forces the call site
  to exist. Phase A's primitive is forward-compatible — a future plan adds
  `infrared: InfraredBridge` to `SandboxBridge` without touching Phase A
  shape.
- **Q2 — Phase A is split into A1 (additive) + A2 (deletion).** A1 adds the
  contextvar branch alongside the existing `install_remote_store`. A2
  deletes `RemoteStore` and the `restore_state` workaround once A1 bakes on
  dev. Window between PRs: days, not weeks.
- **Q3 — Main-side leak guard: docstring rule + assertion now.** The helper's
  docstring documents "never set `current_sandbox` from main-side code". A1
  adds an assertion `current_sandbox.get() is None` before `set()` in
  `sandbox.py` (catches two-runtimes-one-loop accidents). The real
  cross-process test lands with transport T4 — not this plan.

## Why

1. **The current store routing violates the Iron Law.** `install_remote_store`
   rebinds `homeassistant.helpers.storage.Store` at module scope. That's the
   exact pattern v1 was the cautionary tale for (v1 wrote
   `EntityComponent._platforms`; v2 added a public hook). Replace it with a
   declared core HA hook.
2. **The module-rebinding has a known footgun the contextvar primitive
   fixes.** Helpers that do `from .storage import Store` at module-load
   (`restore_state.py`, `area_registry.py`, `entity_registry.py`,
   `device_registry.py`, `issue_registry.py`, `label_registry.py`,
   `floor_registry.py`, `category_registry.py`, `collection.py` — confirmed by
   grep) capture the *original* `Store` reference. The rebinding can't reach
   them, which is why `_load_restore_state` in `sandbox.py:311` has to do the
   explicit `data.store = RemoteStore(...)` workaround. **A contextvar read
   inside `Store.async_load/save/remove` is a single source of truth
   regardless of how `Store` was imported** — every instance method checks the
   contextvar at call time. That workaround can be deleted.
3. **Cross-sandbox calls (IR / RF / BLE / serial) need the same shape.** When
   a sandboxed integration calls `infrared.send(...)` (or `rf.send(...)`, or
   later `ble.connect(...)`), it must reach a producer that may live on main
   or in another sandbox. `if sandbox := current_sandbox.get(): return await
   sandbox.infrared.send(...)` is the user-stated shape; doing it once via a
   `ContextVar` gives every cross-process boundary the same primitive.
   **Deferred to follow-up plans** (see Q1 decision above) — Phase A ships
   only the primitive, with sub-namespaces composing in cleanly later.
4. **Statelessness payoff (`plan-ephemeral-sources.md`).** Once Store goes
   through the contextvar, the sandbox holds zero patched globals — fully
   wipe-and-restart safe.

## Design

### 1. `current_sandbox` ContextVar in core HA

**Precedent confirmed:** `homeassistant/helpers/` already hosts module-level
ContextVars — `helpers/http.py::current_request`,
`helpers/chat_session.py::current_session`, plus several in `helpers/template/`
and `helpers/script.py`. The shape we want is identical to those: module-level
`ContextVar[T | None]` with `default=None`. New file matches that convention.

New file `homeassistant/helpers/sandbox_context.py`:

```python
from contextvars import ContextVar
from typing import Protocol, Any

class SandboxBridge(Protocol):
    """Per-sandbox routing surface, populated by the sandbox runtime."""

    async def async_store_load(self, key: str) -> Any: ...
    async def async_store_save(self, key: str, data: Any) -> None: ...
    async def async_store_remove(self, key: str) -> None: ...

current_sandbox: ContextVar[SandboxBridge | None] = ContextVar(
    "current_sandbox", default=None
)
```

Lives in `homeassistant/helpers/` (not `components/sandbox_v2/`) because core
HA primitives (`Store`) read it. The `SandboxBridge` protocol is the contract;
sandbox_v2 provides the concrete implementation in the client runtime.

**Sub-namespaces (IR / RF / BLE) are deferred** pending Q1. If Phase B
proceeds we extend the protocol then; until then `SandboxBridge` has only the
three store methods.

### 2. `Store` checks the contextvar

`homeassistant/helpers/storage.py` — modify `Store.async_load`,
`Store.async_save`, `Store.async_remove`:

```python
async def async_load(self) -> ...:
    if sandbox := current_sandbox.get():
        return await sandbox.async_store_load(self.key)
    # ... existing local-disk path unchanged ...
```

Same shape for save / remove. The contextvar check is the *first* line so the
local-disk path is fully bypassed.

**Where the migration loop lives — important correction to the draft.**
`Store._async_load_data` (`storage.py:341`) contains the migration block
(`inspect.signature(self._async_migrate_func)…`). That block reads the wrapped
envelope (`{version, minor_version, key, data}`) and may call back into
`self.async_save` to persist the migrated payload. Two choices:

- **(A) Bridge returns the *unwrapped* `data["data"]`** — bridge does the
  migration itself (today's `RemoteStore._async_load_data` does this). Then
  `Store.async_load` -> contextvar branch returns the unwrapped value and
  *skips* the existing migration block entirely for the sandbox path.
  Migration logic is duplicated across `Store._async_load_data` and the bridge.
- **(B) Bridge returns the *wrapped* envelope dict; `Store` runs the
  migration loop.** Refactor `Store.async_load` so the contextvar branch
  fetches the wrapped dict, then falls into the *existing* migration block (it
  doesn't care whether the dict came from disk or from a bridge). The
  inner-loop migration's `self.async_save(stored)` call recurses back through
  the contextvar branch, which is fine.

**Recommendation: (B).** Migration code stays in `Store` (one copy), the
bridge contract is the simpler "fetch wrapped dict by key". Concretely this
means refactoring `_async_load_data` so the "fetch the wrapped data" step is
the only thing that branches on the contextvar; the migration block at
`storage.py:427-460` runs unchanged. The draft's claim "that logic moves to
the bridge implementation" is wrong — keep it in `Store`.

**`Store.__init__` if contextvar isn't set yet.** No behaviour change. `__init__`
does not touch the contextvar. The first IO call resolves it. This matters
because `Store(...)` is often constructed at integration-import time, *before*
`current_sandbox.set(...)` runs. With (B), nothing about the constructor
changes — safe.

**`delay_save` / `final_write`:** unchanged. Those schedule on the `Store`
instance and don't touch disk directly. They eventually call
`async_save`, which hits the contextvar branch.

### 3. Sandbox runtime sets the contextvar + provides the bridge

In `sandbox_v2/hass_client/hass_client/sandbox.py`, replace
`install_remote_store(self._channel)` with:
- Construct a `ChannelSandboxBridge` (new class — implements the
  `SandboxBridge` protocol; the three store methods delegate to the existing
  `MSG_STORE_LOAD` / `MSG_STORE_SAVE` / `MSG_STORE_REMOVE` channel calls,
  including the orjson preserialize step from `RemoteStore._async_write_data`).
- `current_sandbox.set(bridge)` once early in `SandboxRuntime.run`, *before*
  `_load_restore_state` and before any handler registers. The `Token` returned
  by `set` is stashed; teardown does `current_sandbox.reset(token)` for tidy
  test isolation (not strictly required for prod because the process exits).

**ContextVar inheritance — confirmed safe for our model.** Python's
`asyncio.create_task` snapshots `contextvars.copy_context()` at task-creation
time, so every coroutine spawned from `run()` inherits the contextvar.
`Channel._spawn_handler` (`channel.py:229`) creates tasks with
`asyncio.create_task(coro)` — those handler tasks inherit the contextvar as
of the moment the message dispatches. Phase 12's *concurrent* dispatcher
multiplies the handler tasks but each still inherits at its `create_task`
moment, which is post-`current_sandbox.set`. **No re-entrancy hazard.** A
handler that itself issues `channel.call(...)` and awaits a reply doesn't lose
its contextvar — `await` doesn't strip context, only `create_task` boundaries
do, and there's no `create_task` between a handler and the call it issues.

**The `_load_restore_state` workaround can be deleted.** With (B), the
contextvar is set before `_load_restore_state` runs; `RestoreStateData.async_load`
calls `self.store.async_load()`, the store is the original `Store` (captured
at import), and `Store.async_load` reads the contextvar at call time. The
explicit `data.store = RemoteStore(...)` swap is no longer needed. **This is
the architectural win — verify in a test (see Phase A tests).**

### 4. Delete `RemoteStore` + `install_remote_store`

Once `Store.async_load/save/remove` route via contextvar, `RemoteStore` is
dead code. Delete:
- `sandbox_v2/hass_client/hass_client/remote_store.py` (the class and the
  installer)
- The `install_remote_store(...)` call + `uninstall_remote_store()` cleanup
  in `sandbox.py`
- The `data.store = RemoteStore(...)` line in `_load_restore_state`
- `tests/test_remote_store.py` — replace with `tests/test_sandbox_bridge.py`
  testing the contextvar branch through the public `Store` API plus the
  bridge's channel-call mapping.

### 5. ~~Cross-sandbox sub-namespaces (IR / RF as Phase B)~~ — DEFERRED pending Q1

Stripped from this plan until Q1 has a concrete consumer. The contextvar
primitive in §1 is forward-compatible with sub-namespaces: when the first
cross-sandbox IR/RF need lands, add an `infrared: InfraredBridge` attribute to
`SandboxBridge`, populate it in `ChannelSandboxBridge`, and update the
relevant action-handler site to read it. No churn in Phase A's shape.

## Phases

### Phase A1 — Contextvar + dual-path Store routing (no deletes)
- Add `homeassistant/helpers/sandbox_context.py` with `current_sandbox` + the
  `SandboxBridge` Protocol (store methods only; no IR/RF yet).
- Refactor `Store._async_load_data` so the "fetch wrapped dict" step branches
  on `current_sandbox.get()`; migration block stays put (design choice B).
  Modify `async_save` and `async_remove` to early-return through the bridge
  when the contextvar is set.
- Add `ChannelSandboxBridge` in
  `sandbox_v2/hass_client/hass_client/sandbox_bridge.py` (new file). Implement
  the three store methods by calling `MSG_STORE_LOAD`/`MSG_STORE_SAVE`/
  `MSG_STORE_REMOVE` (lift the bodies from `RemoteStore`, including the
  orjson preserialize on save).
- In `SandboxRuntime.run`: construct the bridge, `current_sandbox.set(bridge)`
  **before** `_load_restore_state` and handler registration. `install_remote_store`
  call **stays** in A1 — both paths active, but the contextvar branch fires
  first so it actually serves the IO.
- Tests added in A1:
  1. **`Store(...).async_load` via contextvar reaches the bridge with the
     right key, returns the unwrapped data.** Uses a `_FakeBridge` set on
     `current_sandbox` directly (no channel).
  2. **Migration loop fires through the contextvar path.** Parametrise across
     2-arg and 3-arg `_async_migrate_func` signatures (mirrors
     `test_remote_store.test_migration_runs_when_version_differs`). Asserts
     the post-migration `async_save` recurses back through the bridge.
  3. **Main-process round-trip with `current_sandbox.get() is None` is
     byte-identical to today.** Regression guard for the no-sandbox path.
  4. **`restore_state` warm-load works *without* the
     `data.store = RemoteStore(...)` workaround** — set the contextvar,
     instantiate a `RestoreStateData` against a vanilla `Store`, call
     `async_load`, assert the bridge sees the load. **This is the smoking
     gun that the contextvar fix subsumes the workaround.**
  5. **Contextvar inherits across `asyncio.create_task`.** Set the contextvar
     in the test body, spawn a task that constructs a `Store` and loads, the
     bridge is reached. Catches a future refactor that accidentally creates a
     task before the set.

### Phase A2 — Delete `RemoteStore` + uninstall the workaround

> **Correctness prerequisite surfaced by A1's STATUS (2026-06-03):** A1's
> contextvar branch is in `async_save`, but **`async_delay_save` and the
> FINAL_WRITE flush do NOT call `async_save`** — they go directly through
> `_async_handle_write_data` → `_async_write_data`. While A1 ran, `RemoteStore`
> still overrode `_async_write_data`, so delayed/final-write saves reached
> main. **Once A2 deletes `RemoteStore`, delayed saves would silently land in
> the sandbox tempdir.** A2 must therefore move (or duplicate) the contextvar
> save branch DOWN to `_async_write_data` (which is exactly what
> `RemoteStore._async_write_data` overrode). Branching at `_async_write_data`
> covers `async_save`, `async_delay_save`, and FINAL_WRITE uniformly.

- **First:** add the contextvar branch in
  `homeassistant/helpers/storage.py::Store._async_write_data` (delegate to
  `sandbox.async_store_save(self.key, data)` when the contextvar is set —
  mirrors `RemoteStore._async_write_data`'s body). The branch already in
  `async_save` can either stay (redundant but harmless) or be removed in
  favour of the lower-level one. Recommend removing the `async_save` branch
  so there's a single source of truth.
- Add a regression test exercising `async_delay_save` + the FINAL_WRITE flush
  through the contextvar path: assert that `hass.async_stop` (or the
  EVENT_HOMEASSISTANT_FINAL_WRITE path) flushes pending delayed saves through
  the bridge. Without this, the silent-disk-write regression isn't guarded.
- **Then:** delete `_load_restore_state`'s `data.store = RemoteStore(...)`
  line; let the contextvar handle it.
- Delete `install_remote_store` call + `uninstall_remote_store` in
  `sandbox.py`. Delete `sandbox_v2/hass_client/hass_client/remote_store.py`.
- Delete `sandbox_v2/hass_client/tests/test_remote_store.py`. Tests added in
  A1 + the new delayed-save test cover the cases; no test deletion before
  its replacement is green.
- Update `test_shutdown.py` if it references `install_remote_store` directly
  (per Risks #2 — confirm via grep before deleting).
- Update docs (see Final phase section).

### Follow-up plans (out of scope here — open separately when needed)

- **Cross-sandbox IR / RF** — both are one-way command flows (request → ack).
  Open when a sandbox pair forces the need: add `infrared: InfraredBridge`
  (and `radio_frequency: RadioFrequencyBridge`) to `SandboxBridge`, pick
  the call surface (Q1 options) at that time, wire producer-side dispatch in
  `homeassistant/components/sandbox_v2/bridge.py`.
- **Cross-sandbox BLE / ESPHome serial** — harder: bidirectional stream +
  setup-time enumeration races. Same contextvar primitive but a richer
  protocol. Capture design constraints in its own plan when the work lands;
  the CLAUDE.md follow-up note already documents the shape.

## Touch points

```
homeassistant/helpers/sandbox_context.py                  (NEW — contextvar + Protocol)
homeassistant/helpers/storage.py                          (Store IO methods route via contextvar; migration loop stays)
sandbox_v2/hass_client/hass_client/sandbox_bridge.py      (NEW — ChannelSandboxBridge)
sandbox_v2/hass_client/hass_client/sandbox.py             (set contextvar before warm-load + handlers; drop _load_restore_state workaround; drop install_remote_store in A2)
sandbox_v2/hass_client/hass_client/remote_store.py        (DELETE in A2)
sandbox_v2/hass_client/tests/test_remote_store.py         (DELETE in A2)
sandbox_v2/hass_client/tests/test_sandbox_bridge.py       (NEW in A1)
```

**Audit of "what else gets routed today" (confirmed via grep):** Eight
helpers do `from .storage import Store` at module-load —
`restore_state.py`, `area_registry.py`, `entity_registry.py`,
`device_registry.py`, `issue_registry.py`, `label_registry.py`,
`floor_registry.py`, `category_registry.py`, plus `collection.py`. Today
**only** `restore_state` gets the explicit workaround (because the others'
data is meant to live in the sandbox's tempdir, not main — see
`remote_store.py`'s docstring "Registries that already loaded against the
sandbox-private tempdir keep their local file backing"). The contextvar
approach inherits that semantics naturally: those registries' `Store`s are
constructed *before* the contextvar is set (during `FlowRunner.create`), but
**their first `async_load` call is also before the set today**, so they keep
serving the local file. Verify this ordering in a test:
`restore_state.async_load` happens *after* `current_sandbox.set`, but
`entity_registry.async_load` (called inside `FlowRunner.create`) happens
*before*. If the ordering ever changes such that an `async_load` straddles
the set, that registry would silently start routing to main — flag this
explicitly with a comment in `sandbox.py` next to the `current_sandbox.set`
line.

## Sequencing within Phase A — A1 + A2 split (recommended)

**Argument for one PR (status quo of draft):** Smaller commit graph, no
intermediate state where both paths exist, "atomic" win.

**Argument for A1 + A2 split (recommended):**
- A1 is additive — adding a contextvar branch to three methods doesn't break
  anything in the no-sandbox path (the branch is a no-op when
  `current_sandbox.get() is None`). It can ship and bake on dev for a few
  days without breaking the existing sandbox tests, which still go through
  `install_remote_store`.
- A2 is the deletion. If A1 has a subtle bug — e.g. an ordering issue where a
  `Store` instance somehow gets constructed *and* used before the contextvar
  is set — A1 alone keeps the sandbox working (RemoteStore still takes
  over). A2 makes the contextvar the *only* path; bugs surface immediately
  but rollback is one revert.
- Splitting also lets us land the test for the `restore_state` workaround
  removal in A2 specifically — A1 keeps the workaround so the test isn't
  meaningful there; A2 deletes the workaround and the test asserts the
  contextvar path covers it.

**Recommendation: A1 + A2, two PRs, A2 immediately after A1 lands green on dev.**
A1 stays small (one core HA file + one new helper + one new client file +
tests, ~150 LOC of diff). A2 is mostly deletion. The fast-follow keeps the
window where two paths exist measured in days, not weeks, which addresses
Risk #1.

## Sequencing vs other plans

This plan executes **first**, before:
- `plan-fidelity-batch.md` — independent, but Phase A removes ~200 LOC of
  monkey-patching that the fidelity work shouldn't have to step around.
- `plan-transport.md` — the contextvar primitive is wire-agnostic. Transport
  ships protobuf; the bridge methods read/write protobuf instead of dicts
  after T2 lands. **One coupling to call out:** transport's T4 (WebSocket)
  is the only path that runs main-side code servicing a sandbox call in
  main's event loop — see Risks #3.
- `plan-ephemeral-sources.md` — stateless story is incomplete while Store
  patches a module global. Land contextvar first so the only remaining
  stateful bit really is the on-disk integration code.
- `plan-docker.md` — naturally pairs after Phase A so the container image
  doesn't need to ship a patched-storage workaround.

**Hard dependency: none.** Phase A is a self-contained refactor + small core
HA hook.

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **Storage corruption window during A1→A2 transition.** Both code paths active simultaneously: the contextvar branch fires (correct path); `RemoteStore`'s `_storage.Store` rebinding is also active (legacy path). If anything constructs a `Store` *without* the contextvar branch firing first, it goes through the rebinding. With A1+A2 split, this window exists for the days between PRs. | Low (the contextvar branch is the *first* line of each IO method, so it can't be skipped if set) | High (corruption) | A1 lands a regression test that fails if `RemoteStore` is invoked while `current_sandbox` is set. Plus the test ordering audit above. |
| 2 | **Fixture leakage:** test fixtures across `hass_client/tests/` that rely on `install_remote_store` (`installed_store` fixture in `test_remote_store.py`, plus `test_shutdown.py:210-212` which references the rebinding directly) — `grep -n install_remote_store sandbox_v2/hass_client/tests/` returns those plus `test_shutdown.py`. | Medium | Medium (broken tests, not corruption) | Phase A1's PR must touch `test_shutdown.py` to set the contextvar instead of asserting against the rebinding. Confirmed there's only one test file that does this; the `installed_store` fixture itself goes away with A2. |
| 3 | **Main-side handler accidentally inherits a sandbox contextvar.** Today impossible (sandbox process ≠ main process; different event loops). When transport T4 lands, a main-side WS handler will service a sandbox call **on main's loop**; if anything in main's handler chain does `current_sandbox.set(...)` *for that request scope* and then spawns a task, the task inherits. We don't do this today and aren't planning to — but document the rule "never set `current_sandbox` from main-side code" in the helper's docstring. | Low | High (silent rerouting of main's own Stores to a bridge) | Docstring rule + a test in T4's PR (not this plan's). For Phase A, add an assertion in `sandbox.py` that `current_sandbox.get() is None` *before* we set it — catches the case where two sandbox runtimes share an event loop (unlikely but cheap to assert). |
| 4 | **Performance: every `Store.async_load/save/remove` now does a `ContextVar.get()`.** `ContextVar.get()` is a C-level lookup, ~50ns. Storage IO is at least 4 orders of magnitude slower (disk syscall or RPC round-trip). | Trivial | Trivial | No mitigation needed; mention in PR description if asked. |
| 5 | **Contextvar lost across an unexpected task boundary** (e.g. a future refactor introduces `loop.run_in_executor` followed by a coroutine that constructs a Store on the executor thread). `ContextVar` is copied into asyncio tasks; **`run_in_executor` runs sync code on a thread** and does NOT propagate the asyncio context. Today no `Store` IO crosses an executor boundary, but `_write_data` does call `hass.async_add_executor_job(self._write_prepared_data, …)` for the *write* — that's fine because the contextvar branch returns *before* hitting that line. | Low | High if it ever bites | The Phase A tests include #5 ("contextvar inherits across `asyncio.create_task`") as a regression guard. Add a separate test asserting executor-job paths are NOT entered when the contextvar is set. |
| 6 | **Concurrent dispatcher reentrancy** (Phase 12 made handlers concurrent — `Channel._spawn_handler` uses `asyncio.create_task`). Each handler task inherits the contextvar copy at create time. If a handler issues `channel.call` and that triggers a `Store` write deep in the call's await chain, the contextvar is still set in that task — fine. The hazard is if a handler ever *unsets* the contextvar (it shouldn't, but…). | Trivial (no code path does this) | Medium | The bridge doesn't touch the contextvar; only `SandboxRuntime.run` sets it. Document this in the helper docstring. |

## Verification checklist (Phase A1 + A2)

- [ ] `homeassistant/helpers/sandbox_context.py` matches the conventions of
      `helpers/http.py` and `helpers/chat_session.py` (module-level
      ContextVar, `default=None`, Protocol for the value type).
- [ ] `Store._async_load_data` migration block is untouched; only the
      "fetch wrapped dict" step branches.
- [ ] `_load_restore_state`'s `data.store = RemoteStore(...)` workaround
      is deleted in A2 and the corresponding test (Phase A1 test #4) is
      green.
- [ ] No file outside `sandbox_v2/` (other than `helpers/storage.py` and the
      new `helpers/sandbox_context.py`) is modified by this plan.
- [ ] `grep -rn install_remote_store sandbox_v2/ homeassistant/` returns
      empty after A2.
- [ ] `uv run pytest tests/components/sandbox_v2/ --no-cov -q` and
      `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
      both pass.
- [ ] `uv run prek run --files <changed>` clean.

## Final phase — docs up to date

Close with the cross-cutting docs phase (`plan-v1-removal.md` Phase D):
- `sandbox_v2/CLAUDE.md` "Core HA files modified" — add the
  `helpers/sandbox_context.py` and `helpers/storage.py` rows. Note this is
  the **fourth** core HA file v2 touches.
- `sandbox_v2/OVERVIEW.md` "Store routing" — rewrite around the contextvar.
  Delete the "explicit `RemoteStore` for restore_state" paragraph (the
  workaround is gone).
- `sandbox_v2/docs/FOLLOWUPS.md` — close the "do not monkey-patch private
  internals" tension noted re: store patching.
- `sandbox_v2/architecture.html` — sections referencing `RemoteStore` and
  `install_remote_store` (lines ~93, ~206, ~244-246, ~336-339, ~536-546, ~644).
- Remove the "RemoteStore patch" language from OVERVIEW / FOLLOWUPS / any
  STATUS file that's still current-state (leave historical STATUS-phase-*
  records intact).
