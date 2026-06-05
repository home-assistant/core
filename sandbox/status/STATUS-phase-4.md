Status: DONE

Phase 4 delivers the "perfect flow" end-to-end. The HA Core
`ConfigEntries` gains a single `router` attribute consulted from
`ConfigEntriesFlowManager.async_create_flow` and `ConfigEntries.async_setup`;
sandbox_v2 plugs in a `SandboxFlowRouter` that hands sandbox-bound flows
to a `SandboxFlowProxy` `ConfigFlow` and intercepts setup of entries
tagged `__sandbox_group`. Manager and runtime now share a JSON-line
`Channel` over the subprocess's stdin/stdout (post-marker); the sandbox
runtime hosts a private `HomeAssistant` and a `FlowRunner` that drives
the real integration's `ConfigFlow` inside a `_SandboxFlowManager` (a
`ConfigEntriesFlowManager` subclass that short-circuits CREATE_ENTRY so
the sandbox never tries to add an entry to its private store — main is
the canonical owner). FlowResults are marshalled by stripping the live
`data_schema` (Phase 5 work) and copying a known safe-fields list; the
proxy re-issues `async_show_form` / `async_create_entry` /
`async_abort` so the framework treats the result as native.
`__getattribute__` (not `__getattr__`) intercepts every `async_step_*`
because ConfigFlow declares several step methods at the class level.

Files added:
- `homeassistant/components/sandbox_v2/channel.py`
- `homeassistant/components/sandbox_v2/proxy_flow.py`
- `homeassistant/components/sandbox_v2/router.py`
- `sandbox_v2/hass_client/hass_client/channel.py`
- `sandbox_v2/hass_client/hass_client/flow_runner.py`
- `sandbox_v2/hass_client/tests/test_flow_runner.py`
- `tests/components/sandbox_v2/_helpers.py`
- `tests/components/sandbox_v2/test_channel.py`
- `tests/components/sandbox_v2/test_phase4_subprocess.py`
- `tests/components/sandbox_v2/test_proxy_flow.py`
- `tests/components/sandbox_v2/test_router.py`

Files changed:
- `homeassistant/components/sandbox_v2/__init__.py` — wire the manager
  and router into `async_setup`; register `EVENT_HOMEASSISTANT_STOP`
  cleanup; expose `SandboxV2Data { manager, router, channels }`.
- `homeassistant/components/sandbox_v2/manager.py` — `SandboxProcess`
  now opens a `Channel` over the subprocess pipes after the ready
  marker, exposes `process.channel`, and invokes an
  `on_channel_ready(group, channel)` callback so the router can wire
  per-sandbox handlers. `SandboxManager.__init__` accepts the callback;
  subprocess spawn now requests `stdin=PIPE`.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — Phase 3 stub
  upgraded to Phase 4: builds a `FlowRunner` against a private
  `HomeAssistant` (with a temp config_dir if none provided), prints the
  ready marker, then opens a stdio `Channel`, registers
  `sandbox_v2/ping` + the flow handlers, and runs until shutdown. New
  `channel_factory` constructor parameter lets tests skip the stdio
  channel (pytest captures stdin).
- `sandbox_v2/hass_client/tests/test_sandbox_runtime.py` — Phase 3
  shutdown test now passes a noop channel factory; the real stdio path
  is covered by the new HA-core subprocess test.
- `tests/components/sandbox_v2/test_init.py` — assertions updated for
  the new `SandboxV2Data` shape and the router registration.
- `sandbox_v2/plan.md` — Phase 4 section marked complete with summary
  and inline notes on deferrals.

Core HA files modified (review surface):
- `homeassistant/config_entries.py` — 1 new attribute
  `ConfigEntries.router: ConfigEntryRouter | None`, plus the
  `ConfigEntryRouter` `Protocol` defining its two methods. Call sites:
  `ConfigEntriesFlowManager.async_create_flow` (consults
  `async_create_flow`) and `ConfigEntries.async_setup` (consults
  `async_setup_entry`). The plan called for both intercept points; both
  consult the same attribute so the surface stays minimal. Iron Law:
  no monkey-patching of private internals.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → **43 passed**
  (28 from Phase 0–3 + 15 new: 5 channel, 6 router, 3 proxy flow, 1
  subprocess e2e).
- `cd sandbox_v2/hass_client && uv run pytest -q` → **7 passed** (3
  from Phase 3 + 4 new: flow runner init / step / errors / abort).
- `uv run pytest tests/test_config_entries.py --no-cov -q` → **383
  passed, 4 snapshots passed** — the core hook is benign when no router
  is installed.
- `uv run prek run --files <17 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **`async_setup_entry` is a Phase-4 stub.** The router currently marks
  a sandboxed entry LOADED as soon as the sandbox process starts. Phase
  5 needs to replace this with a real round-trip — push the entry's
  domain/data/options/version to the sandbox, have the sandbox load the
  integration and call `async_setup_entry` against the proxied entry,
  and return success/failure to the router. The hook point is
  `SandboxFlowRouter.async_setup_entry` in `router.py`.
- **`data_schema` is stripped on the wire.** The FlowRunner sets
  `_has_data_schema: True` when it stripped a schema, and the proxy
  logs a debug message when it sees that flag. Phase 5 must add a
  serialised-schema bridge (voluptuous_serialize.convert on the
  sandbox side, a tiny wrapper that voluptuous_serialize can re-emit on
  main) so the frontend actually renders forms for sandboxed flows.
- **`unique_id` is not propagated from sandbox to main.** When a
  sandboxed flow calls `self.async_set_unique_id(...)`, the unique_id
  lives in the sandbox's `flow.context` but is never reflected onto the
  proxy's `flow.context`. The framework's duplicate detection on main
  will miss this. Phase 4 only exercises flows without unique_id;
  Phase 5 should include `flow.context["unique_id"]` in every
  marshalled result and apply it to the proxy.
- **Periodic ping loop is still not running.** The `sandbox_v2/ping`
  handler exists and is exercised by the subprocess test, but nothing
  drives it on a timer. A 30-second loop in `SandboxManager` (or a
  per-process watchdog task) is the next ergonomic improvement once
  there are real production-leaning paths.
- **`SandboxFlowProxy.async_remove`'s fire-and-forget abort task.** It
  stashes the task in a module-level `_BACKGROUND_ABORTS` set to keep
  the GC away from it; the alternative (a per-manager set) was a layer
  of indirection that pylint didn't love and Phase 5 doesn't yet need.
  If Phase 5 grows additional background tasks, hoisting both onto the
  manager makes sense.
- **`ConfigEntryRouter` `Protocol` lives in `config_entries.py`.** It
  is not exported via `homeassistant.config_entries`'s `__all__` (the
  file has no `__all__`). Phase 5+ may want to make the contract more
  prominent — for now `SandboxFlowRouter` documents the structural
  conformance in its docstring rather than inheriting from the
  Protocol class (to avoid coupling at import time).
- **The `ignore_translations_for_mock_domains` fixture in
  `test_proxy_flow.py`** is a workaround for the conftest's
  translation-validation step against `mock_integration` domains.
  Phase 5's tests that use real integrations won't need it.
