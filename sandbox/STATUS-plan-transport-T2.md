# STATUS — plan-transport T2 (protobuf wire + typed handlers)

**One-line:** T2 shipped green — the control channel now speaks typed
protobuf messages end-to-end (default codec = `ProtobufCodec`), ~20 handlers
and ~69 test call/push sites converted in one atomic commit, both suites green,
prek clean.

**Commit:** `360e4543300` — `sandbox_v2: protobuf wire + typed handlers (transport T2)`
(64 files, +3762/-1046). Not pushed — parent pushes.

## Test results (exact)

- HA core: `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **189 passed, 18 warnings** (T1 was 183; +6 from the new
  `test_proto_transport.py`).
- Client: `uv run pytest sandbox_v2/hass_client/ -q` → **53 passed, 1 warning**.
- `uv run prek run --files <60 touched non-gencode files>` → all hooks pass
  (ruff, ruff-format, codespell, json, yamllint, prettier, mypy, pylint,
  gen_requirements_all, hassfest, hassfest-metadata).
- Drift guard: `prek run --hook-stage manual sandbox-v2-proto-drift` → Passed
  (regenerates both mirrors in an isolated venv, `git diff --exit-code` clean).

## Greps that came back empty (as required)

- `grep -rn from_payload homeassistant/components/sandbox_v2/ sandbox_v2/hass_client/hass_client/` → **empty** (all dict constructors replaced by `from_proto` / `make_entity_description`).
- `grep -rn "class WebSocketTransport|WebSocketTransport("` → **empty** (no WS code introduced; only docstring references to the future drop-in seam, unchanged from T1).
- `grep -rn "parent_id|user_id" sandbox_v2/hass_client/hass_client/` → only the two **comments** ("Forward only the context id — never parent_id / user_id") in `event_mirror.py` + `entity_bridge.py`. No wire-shaped occurrences — the sandbox never serializes `parent_id`/`user_id`.

## What changed, file by file

### New
- `sandbox_v2/proto/sandbox_v2.proto` — single source of truth.
- `sandbox_v2/proto/generate.sh` — regen into both mirrors via an isolated
  `/tmp` venv pinned to `protobuf==6.32.0` (verified `grpcio-tools==1.80.0`).
- `sandbox_v2/proto/check_drift.sh` — drift guard wrapper (degrades gracefully
  when `uv` is absent).
- `homeassistant/components/sandbox_v2/_proto/sandbox_v2_pb2.py(+.pyi)` and
  `sandbox_v2/hass_client/hass_client/_proto/sandbox_v2_pb2.py(+.pyi)` —
  checked-in gencode (two no-cross-import mirrors).
- `…/messages.py` (both sides, byte-identical) — the `type → (request_cls,
  result_cls)` REGISTRY + `struct_to_dict`/`dict_to_struct`/`listvalue_to_list`/
  `list_to_listvalue` helpers + `device_info_to_proto` + `make_entity_description`.
- `…/codec_protobuf.py` (both sides, byte-identical) — `ProtobufCodec`.
- `tests/components/sandbox_v2/test_proto_transport.py` — 6 new tests (round-trip
  byte-identity, Error/MultipleInvalid round-trip, `_resolve_context`,
  state_changed Context security).

### Production handlers converted (~20)
- HA `bridge.py`: `_handle_register_entity` (EntityDescription→RegisterEntityResult),
  `_handle_unregister_entity`, `_handle_state_changed`, `_handle_register_service`,
  `_handle_unregister_service`, `_handle_fire_event`, `_handle_store_load/save/remove`,
  `_raw_call_service` + the service forwarder; `SandboxEntityDescription.from_proto`,
  `_deserialise_device_info(pb.DeviceInfo)`, `_validate_key`; **new
  `_resolve_context` + `_async_system_user_id`**.
- HA `router.py`: `_entry_setup_payload`→`pb.EntrySetup`, entry_setup/unload result reads.
- HA `proxy_flow.py`: flow_init/step/abort send protos; FlowResult field reads.
- HA `manager.py` / `__init__.py`: channel built with `ProtobufCodec`; shutdown
  reply consumed as `pb.ShutdownResult`.
- HA `entity/__init__.py` + `entity/{button,event,notify,scene}.py`:
  `sandbox_apply_state` gained an optional `context` param threaded to
  `async_set_context`.
- Client `entry_runner.py`, `flow_runner.py` (incl. `_marshal_result`→FlowResult),
  `entity_bridge.py`, `service_mirror.py`, `event_mirror.py`, `sandbox_bridge.py`,
  `sandbox.py` (ping/shutdown return protos; channel built with `ProtobufCodec`).

### Tests converted (~69 sites)
- HA: `test_bridge` (18), `test_store` (13), `test_phase13_proxies` (28),
  `test_phase14`, `test_phase19_devices`, `test_perf`, `test_phase4_subprocess`,
  `test_phase9_shutdown`, `test_proxy_flow`, **`test_router`**,
  `test_testing_plugins`. `test_channel` stays JSON via `make_channel_pair(use_json=True)`.
- Client: `test_entry_runner`, `test_flow_runner`, `test_entity_bridge`,
  `test_service_mirror`, `test_event_mirror`, `test_sandbox_bridge`,
  `test_shutdown`, `test_testing_inproc`.
- `tests/.../_helpers.py` + `hass_client/testing/_inproc.py`: channel pairs now
  default to `ProtobufCodec`; `_helpers.make_channel_pair(use_json=True)` selects
  the registry-free `JsonCodec` for channel-core tests.

## Final proto schema shape (and deviations from the locked plan)

Implemented as the plan's T2 refinements specify: `EntityDescription` wraps
`EntityInfo{Description, DeviceInfo}` + `InitialState{state, capabilities,
attributes}`; `ServiceResponse{Struct data}` inside
`CallServiceResult{optional ServiceResponse response}` (proto3 `optional`, no
`has_response`); `StateChanged` flattened with `optional context_id`;
`FireEvent` with `optional context_id`. Deviations / additions to flag:

1. **`Error` gained `bool multiple = 4`** (beyond the plan's
   `{message, type, repeated invalid}`) so a single `vol.Invalid` and a
   `vol.MultipleInvalid` are faithfully distinguished on decode (fidelity #7).
2. **`FlowResult` carries only the FORM / CREATE_ENTRY / ABORT fields** the
   main-side proxy actually consumes (type, flow_id, handler, step_id, reason,
   title, description, last_step, preview, version, minor_version, + Struct
   data/options/errors/description_placeholders/context, + ListValue
   data_schema, + has_data_schema). `menu_options`/`subentries`/`url`/
   `progress_action`/`translation_domain` are intentionally dropped — the proxy
   already aborts noisily on any non-FORM/CREATE/ABORT result (the existing
   Phase-4 limitation), so they were never read.
3. **`EntryUnloadResult` has no `reason` field.** The old dict returned
   `{"ok": False, "reason": …}` on failure but the router only ever read `ok`;
   the failure is still logged via `_LOGGER.exception`. No behavior lost.
4. **`DeviceInfo`** models the keys the entity bridge forwards
   (`identifiers`/`connections` as `repeated DevicePair`, `via_device` as one
   pair, `entry_type` as string, the scalar string keys); unset scalars (default
   `""`) are treated as absent on the main side.

## Deviations from the brief worth the parent's eye

1. **`Channel.__init__`'s default codec stays `JsonCodec`** (not
   `ProtobufCodec`). The dispatch core in `channel.py` is kept free of any proto
   import; every *production* channel-construction site (`manager._open_channel`,
   the runtime's stdio factory) and the in-memory real-handler test helpers build
   `ProtobufCodec(REGISTRY)` explicitly. This is the same spirit as T1's
   deviation #1 (keep the core constructor stable) and satisfies "default codec
   is protobuf [in production]; JsonCodec retained for test wire."
2. **`JsonCodec` was NOT converted to "proto-as-JSON".** It stays the
   registry-free, dict-passthrough T1 codec. Reason: `test_channel.py` exercises
   the concurrency-critical channel core with *synthetic* message types
   (`test/echo`, …) and arbitrary dict/int payloads — a registry-aware JsonCodec
   would break exactly the tests that prove the core. The brief's hard
   requirement ("JsonCodec retained for the test wire only") is met; the
   plan/brief's softer "proto-as-JSON via MessageToDict" suggestion was traded
   for keeping the channel-core test wire intact. A separate proto-as-JSON debug
   codec can be added later if wanted (it does not gate T3/T5).
3. **`grpcio-tools` / `mypy-protobuf` are NOT added to any project requirements.**
   Per T1's verified warning, installing grpcio-tools into the project venv bumps
   `protobuf` past the pinned `6.32.0`. `generate.sh` + `check_drift.sh` bootstrap
   a throwaway venv instead. The drift guard is therefore a **manual-stage prek
   hook** (`sandbox-v2-proto-drift`) / dedicated CI lane, not an every-commit
   hook, and skips gracefully when `uv` is absent.
4. **Sandbox-side `context_id → Context` cache: minimal / not added as a
   separate dict.** The substantive piece — the main-side `_resolve_context`
   resolver + cache — is implemented and tested. On the sandbox side, outbound
   `state_changed` / `fire_event` simply forward `state.context.id` /
   `event.context.id`; no current path needs to map an *incoming* context_id back
   to a Context on the sandbox (main→sandbox `call_service` carries a context_id
   but the sandbox's `services.async_call` does not consume it today), so the
   planned in-runtime dict would be dead state. Easy to add when a consumer
   appears.

## Anything weird (edge cases + the one real gotcha)

- **Struct numbers are doubles.** Dynamic fields crossing as
  `google.protobuf.Struct` (service_data, target, attributes, capabilities, the
  wrapped Store envelope, flow data/errors/context) come back with `int` →
  `float` (`255` → `255.0`). Python `==` treats them equal, so every ported dict
  assertion still holds with its exact expected value; nothing was loosened.
  Documented in `messages.py`. Anything with real integer semantics
  (`version`, `minor_version`, `supported_features`) is an explicit `int32`
  field, not a Struct value, so it is unaffected.
- **Assertion-semantics shifts** (each carries an inline comment, no value
  loosened): `result is None` → `not result.HasField("response")`
  (CallServiceResult); `result["restore_state"] is None` →
  `not result.HasField("restore_state")` (ShutdownResult); `loaded is None` →
  `not loaded.HasField("data")` (StoreLoadResult); `result == {}` → empty
  `FlowAbortResult`.
- **Synthetic test handlers must return proto results.** A handler registered in
  a test (e.g. a fake `register_entity` receiver) now has to return the typed
  result message (`pb.RegisterEntityResult(...)`) even where the production
  caller ignores the result — the codec raises `TypeError` on a non-proto
  handler return body. Called out by the conversion agents.
- **The one real gotcha (caught + fixed):** `test_router.py` had an
  `entry_setup` stub returning a plain `dict`. Under `ProtobufCodec` the handler
  return can't be encoded, the response frame is silently dropped, and the
  router's `channel.call(MSG_ENTRY_SETUP)` (no timeout) **hangs forever**. This
  surfaced only in the full-suite run (the file wasn't in the original
  conversion list). Lesson for T3/T5: any test stub that registers a
  `sandbox_v2/*` handler must return a typed proto, or the call hangs rather than
  failing fast.

## T3 + T5 status

**Both unblocked.** T3 (`UnixSocketTransport`) reuses `StreamTransport`'s
length-prefixed framing and is entirely codec-agnostic — the protobuf switch
doesn't touch it. T5 (docs/cleanup) can now describe `ProtobufCodec` as the
production default and `JsonCodec` as the test wire; the `whats-changed.md`
transport boxes (protobuf wire / typed handlers) can be ticked with this SHA.
