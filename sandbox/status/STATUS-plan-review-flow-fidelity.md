# STATUS — plan-review-flow-fidelity (review follow-up #4 of 5)

**Outcome: COMPLETE.** All 3 phases shipped, each as its own commit on
`sandbox` (local only — the orchestrator pushes). A regression test
accompanies every fix; both suites and the proto drift guard are green.

This plan closes three correctness gaps in the config-flow forwarding layer
(`proxy_flow.py` on main, `flow_runner.py` on the sandbox client) so a
sandboxed integration's config flow behaves like a local one.

## What each phase shipped

### Phase 1 — carry version / minor_version / options on create_entry
Commit: *carry version/minor_version/options on create_entry (Phase 1)*

The proxy CREATE_ENTRY path read only `data`/`title`/`description` and called
`async_create_entry`, which stamped the **proxy class** defaults `VERSION=1` /
`MINOR_VERSION=1` / `options={}`. A sandboxed flow with `VERSION>1` lost its
schema version (a spurious migration ran on next setup) and silently dropped
`options`.

- The proxy CREATE_ENTRY branch now reads `version`/`minor_version`/`options`
  off the wire `FlowResult` and overrides the **proxy instance's**
  `self.VERSION`/`self.MINOR_VERSION` before calling `async_create_entry`, and
  passes `options=` through.
- **Instance-vs-class VERSION finding (the plan's open question):**
  `ConfigFlow.async_create_entry` (`config_entries.py:3485-3489`) sets
  `result["minor_version"] = self.MINOR_VERSION` and
  `result["version"] = self.VERSION` — both are **instance** attribute reads,
  so overriding `self.VERSION` on the proxy instance is honoured. No need to
  build the `ConfigFlowResult` dict by hand. `options` is already a first-class
  `async_create_entry(options=…)` parameter. The behaviour is pinned by
  `test_create_entry_carries_version_and_options`, which asserts the proxy
  class default is still `VERSION=1` while the created entry carries `version=2`.
- The wire already carried these fields (`flow_runner._marshal_result` emits
  `version`/`minor_version` and `options` via `_STRUCT_FIELDS`); no proto change
  was needed for Phase 1.

Tests: `test_create_entry_carries_version_and_options` (main),
`test_create_entry_marshals_version_and_options` (client, pins the sender).

### Phase 2 — async_show_menu support + don't leak the sandbox-side flow
Commit: *support async_show_menu + stop leaking flow on unsupported types (Phase 2)*

**MENU support WAS added end-to-end** (not just the leak fix). The proto
toolchain works in this environment (isolated `uv` venv, cached, no network),
so a faithful representation was feasible:

- **Proto change:** added `FlowResult.menu_options` (a `ListValue`, field 19)
  and `optional bool sort` (field 20). Gencode regenerated for **both** mirrors
  via `sandbox/proto/generate.sh`; drift guard green.
- `flow_runner._marshal_result` emits `menu_options` + `sort`. A `list[str]`
  menu crosses as a list of step-id strings; a `dict[str,str]` (id → label)
  menu crosses as a list of `[id, label]` pairs so order **and** labels survive
  (`_marshal_menu_options`).
- The proxy rebuilds the original shape (`_reconstruct_menu_options`) and
  re-issues `self.async_show_menu(...)`. Because the framework dispatches
  `async_step_<chosen>` for the selected option, the proxy translates that into
  the sandbox flow's `{"next_step_id": <chosen>}` navigation choice
  (`_awaiting_menu_selection` state in `_forward_step`).
- **Leak fix (the mandatory minimum):** the remaining unsupported result types
  (EXTERNAL_STEP / SHOW_PROGRESS) no longer set `_terminated=True` before
  aborting. The sandbox-side flow is still in progress for those, so
  `async_remove` must still fire the `flow_abort` RPC to reap it — otherwise a
  flow that set a `unique_id` wedged retries on `already_in_progress` until the
  sandbox restarted. CREATE_ENTRY and the sandbox-sent ABORT still set
  `_terminated` (their sandbox flow is already gone, so no `flow_abort` is owed).

Tests: `test_menu_flow_renders_and_navigates`,
`test_menu_dict_options_round_trip`,
`test_unsupported_result_type_aborts_and_reaps_sandbox_flow` (main);
`test_menu_marshals_options`, `test_marshal_menu_options_dict_keeps_labels`
(client).

### Phase 3 — survive discovery-sourced flow payloads
Commit: *survive discovery-sourced config flows (Phase 3)*

Discovery flows fed the proxy non-JSON objects — a `*ServiceInfo` dataclass
(with `IPv4Address` fields, sets, …) as the first-step `user_input`, and a
`DiscoveryKey` dataclass in `context`. `dict_to_struct` couldn't hold them and
raised `ValueError`/`AttributeError` that the channel-only `except` didn't
catch, crashing the discovery flow unhandled. The router routes
discovery-sourced flows to the sandbox with no source filter
(`router.py:68-84`), so this was reachable.

- **Main side:** `_to_jsonable` walks `context` + the first-step payload into
  Struct-safe primitives before `dict_to_struct` (dataclasses →
  field dicts via `dataclasses.fields`, `IPv4Address`/`IPv6Address` → `str`,
  sets/tuples → lists, bytes → utf-8). Used the existing HA-aware coercion
  intent (a focused walk that also covers IP addresses, which
  `json_bytes`/`json_loads` does **not**); per the brief, the simplification
  plan (#5) will dedupe coercers later. The `except` in `_forward_step` was
  broadened with `(TypeError, ValueError)` to abort cleanly as a backstop for
  any unmapped payload that still trips the marshaller.
- **Sandbox side:** `_rehydrate_discovery` rebuilds the real `DiscoveryKey`
  (`from_json_dict`) and the source's `BaseServiceInfo` so `async_step_<source>`
  receives the type it expects (not a plain dict).
- **Discovery sources mapped** (both directions), per the plan's
  enumeration of what routes to a sandbox:
  - `zeroconf` → `ZeroconfServiceInfo` (IP strings → `ip_address()`)
  - `homekit` → `ZeroconfServiceInfo` (homekit reuses the zeroconf info type)
  - `ssdp` → `SsdpServiceInfo` (set-typed fields restored)
  - `dhcp` → `DhcpServiceInfo`
  - `usb` → `UsbServiceInfo`
  - `hassio` → `HassioServiceInfo`
  - `mqtt` → `MqttServiceInfo`
- **Backstop:** `bluetooth` is intentionally **unmapped** (its info is an
  external `home_assistant_bluetooth.BluetoothServiceInfo` that isn't trivially
  rebuildable) — an unmapped source leaves `data` as a dict, and any
  reconstruction failure degrades to the dict, with the proxy's broadened abort
  as the outer net. Nothing crashes either way.

Tests: `test_discovery_flow_marshals_service_info` (main, the original crash
case); `test_zeroconf_discovery_rebuilds_service_info`,
`test_rehydrate_discovery_rebuilds_objects`,
`test_rehydrate_discovery_unmapped_source_keeps_dict` (client).

## Proto changes

`sandbox/proto/sandbox.proto`: added `FlowResult.menu_options`
(`google.protobuf.ListValue`, field 19) and `optional bool sort` (field 20).
Gencode regenerated into both checked-in mirrors
(`homeassistant/components/sandbox/_proto/` and
`sandbox/hass_client/hass_client/_proto/`) — drift guard green.

## Tests added

Main (`tests/components/sandbox/test_proxy_flow.py`):
`test_create_entry_carries_version_and_options`,
`test_menu_flow_renders_and_navigates`, `test_menu_dict_options_round_trip`,
`test_unsupported_result_type_aborts_and_reaps_sandbox_flow`,
`test_discovery_flow_marshals_service_info`.

Client (`sandbox/hass_client/tests/test_flow_runner.py`):
`test_create_entry_marshals_version_and_options`, `test_menu_marshals_options`,
`test_marshal_menu_options_dict_keeps_labels`,
`test_zeroconf_discovery_rebuilds_service_info`,
`test_rehydrate_discovery_rebuilds_objects`,
`test_rehydrate_discovery_unmapped_source_keeps_dict`.

## Final verification

```
# HA-core sandbox suite (deterministic order)
uv run pytest tests/components/sandbox/ --no-cov -q -p no:randomly
245 passed, 2 warnings in 8.33s

# Client suite (separate uv env)
cd sandbox/hass_client && uv run pytest . -q
104 passed, 1 warning in 0.62s

# Proto drift guard
bash sandbox/proto/check_drift.sh
sandbox proto drift guard: gencode matches sandbox.proto.

# prek on all changed files
ruff check / ruff format / codespell / prettier / mypy / pylint .... Passed
```

**Known pre-existing flake (not caused by this plan):**
`test_proto_transport.py::test_protobuf_codec_round_trip_is_byte_identical`
fails intermittently in *random-order* full-file runs (protobuf `Struct` map
ordering is non-deterministic). It passes in isolation and in deterministic
order (`-p no:randomly`, the 245-pass run above). Re-ran to confirm, as the
brief instructs, then proceeded.
