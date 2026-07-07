# Plan: Sandbox v2 transport + protobuf rewrite (#3)

> Separate, larger effort from the fidelity batch. Goal: replace the JSON-line
> over stdin/stdout wire with a **protobuf** wire over a **pluggable transport**
> (stdio + unix socket + websocket). Decision from brainstorm: typed protobuf
> messages for the known-field payloads; `Struct`/`ListValue` only for the
> genuinely dynamic fields (serialized voluptuous schema, `service_data`, state
> attributes, capabilities).

## Current state (verified)

- **Channel** (`homeassistant/components/sandbox_v2/channel.py` +
  `sandbox_v2/hass_client/hass_client/channel.py`, near-identical mirrors):
  `call`/`push`/`register` + an id→future pending map + a 16-slot inflight
  semaphore. Dispatch is **transport/codec-agnostic already** — only `_write`
  (JSON+`\n`) and `_read_loop` (`reader.readline()` + `json.loads`) are
  encoding/framing-bound.
- **Frames:** call `{id,type,payload}`, response `{id,ok,result|error,
  error_type}`, push `{type,payload}`. 13 message types in `protocol.py`
  (4 main→sandbox, 9 sandbox→main).
- **Transport:** stdio only. Manager spawns `python -m hass_client.sandbox_v2`
  with `stdin/stdout/stderr=PIPE` (`manager.py:_run_one`), scans **stdout** for
  the text marker `sandbox_v2:ready` (`_await_ready`), then wraps
  `Channel(proc.stdout, proc.stdin)`. Runtime writes the marker to stdout then
  hands stdout to asyncio (`sandbox.py:run` ~:157); logs go to **stderr**.
- **Deps:** `protobuf==6.32.0` already in `homeassistant/package_constraints.txt`
  (and `types-protobuf` in `requirements_test.txt`). **No `.proto`/`_pb2.py` in
  core today** — integrations consume pre-generated protobuf from PyPI deps.
  `grpcio` is present but we do **not** need gRPC — just `protobuf` message
  serialization over our own transports.

## Target architecture — three layers

```
Channel  (unchanged dispatch core: pending map, semaphore, register/call/push)
  │  encodes/decodes Frame via ↓
Codec    (Frame <-> bytes)   ── ProtobufCodec (target);  JsonCodec (kept for tests/migration)
  │  reads/writes whole message blobs via ↓
Transport (read_frame()->bytes|None, write_frame(bytes), close())
       ├─ StreamTransport      length-prefixed (4-byte BE len + body) over StreamReader/Writer  → stdio, unix socket
       └─ WebSocketTransport   aiohttp WS binary frames (native framing, no length prefix)
```

- `Channel.__init__` takes a `Transport` + `Codec` instead of a raw
  reader/writer. `_write` → `codec.encode(frame)` → `transport.write_frame`.
  `_read_loop` → `transport.read_frame()` → `codec.decode(bytes)` → `_dispatch`.
- **`_dispatch`, `_run_call_handler`, `_run_push_handler`, the inflight
  semaphore, the pending-id map, `close()` — all unchanged.** This is the
  refactor's safety property: the concurrency-critical core doesn't move.
- **Framing:** stdio/unix use a 4-byte big-endian length prefix; **cap max
  frame size** (e.g. 16 MiB) and abort the channel on overflow — defends the
  host from a compromised sandbox sending a huge length (same hardening spirit
  as `_require_key`). WS uses native binary frames (already bounded by aiohttp).

## Protobuf schema (`sandbox_v2.proto`)

Single source of truth; **generated `_pb2.py` + `_pb2.pyi` checked into the
repo** (core has no build-time protoc — see Codegen below).

**T2 refinements (locked 2026-06-03 — direct user direction):**
- **Group fields the way HA organizes them.** `EntityDescription` (wire) gets
  an `EntityInfo` sub-message (identity: HA's `EntityDescription` dataclass
  fields + `DeviceInfo`) and an `InitialState` sub-message (runtime: initial
  `state` + `capabilities` + initial `attributes`). Mirrors the HA mental
  model, not the wire's historical flat shape.
- **`ServiceResponse` is a typed message** (was `Struct` in the draft) so
  every call-service response goes through the same typed envelope; the
  dynamic payload sits inside it.
- **`StateChanged` carries `Context`.** Was missing.
- **Context handling — security model:** the wire only ever carries
  `context_id` (a string). `parent_id` and `user_id` are NEVER on the wire
  from sandbox → main. Main owns the authoritative `Context` objects; the
  sandbox holds a local cache of `context_id → Context` populated by main
  (e.g. when main pushes a state-changed / fire_event from a context the
  sandbox needs to know about, or when a `call_service` originates on
  sandbox and main mints + returns the resolved `context_id`). Sandbox
  cannot fabricate `parent_id` / `user_id`; main resolves the context_id
  to its own authoritative `Context` at dispatch time.

```proto
syntax = "proto3";
import "google/protobuf/struct.proto";

// Envelope. `type` keeps the existing string-keyed dispatch; `payload` is the
// serialized typed message for that type. One oneof keeps call/response/push
// distinct without sentinel fields.
message Frame {
  uint32 id = 1;            // 0 = push (no reply)
  string type = 2;          // e.g. "sandbox_v2/register_entity"; set on responses too
  oneof body {
    bytes request = 3;      // serialized request message (call or push)
    Response response = 4;
  }
}
message Response {
  bool ok = 1;
  bytes result = 2;         // serialized result message
  Error error = 3;          // set when ok = false
}
// Carries #7's structured voluptuous data natively.
message Error {
  string message = 1;
  string type = 2;          // exception class name
  repeated InvalidError invalid = 3;   // 1 entry = vol.Invalid; N = MultipleInvalid
}
message InvalidError { string message = 1; repeated string path = 2; }

// --- Typed payloads (known fields) ---

// Outer wire message for register_entity. Sub-messages group by HA's own
// organization: EntityInfo = identity; InitialState = runtime starting state.
message EntityDescription {
  string entry_id = 1;
  string domain = 2;
  string sandbox_entity_id = 3;
  optional string unique_id = 4;
  bool has_entity_name = 5;
  EntityInfo info = 6;
  InitialState initial = 7;
}

// Identity: mirrors HA's homeassistant.helpers.entity.EntityDescription
// dataclass + the entity's DeviceInfo. Nested `Description` keeps the
// inner type unambiguous next to the outer `EntityDescription` wire type.
message EntityInfo {
  message Description {
    optional string name = 1;
    optional string icon = 2;
    optional string entity_category = 3;
    optional string device_class = 4;
    int32 supported_features = 5;
    optional string translation_key = 6;
  }
  optional Description description = 1;
  optional DeviceInfo device_info = 2;
}

// Runtime starting state — everything HA needs to surface the entity for
// the first time.
message InitialState {
  optional string state = 1;
  google.protobuf.Struct capabilities = 2;   // dynamic → Struct
  google.protobuf.Struct attributes = 3;     // dynamic → Struct
}

message DeviceInfo { /* identifiers, connections, name, manufacturer, model,
  sw_version, hw_version, via_device, entry_type, configuration_url, ... — all
  known DeviceInfo TypedDict keys as explicit fields */ }

message CallService {
  string domain = 1; string service = 2;
  google.protobuf.Struct target = 3;        // dynamic → Struct
  google.protobuf.Struct service_data = 4;  // dynamic → Struct
  optional string context_id = 5;           // wire-safe: only the id
  bool return_response = 6;
}
message ServiceResponse {
  google.protobuf.Struct data = 1;          // dynamic → Struct
}
message CallServiceResult {
  optional ServiceResponse response = 1;    // unset when return_response was false
}

// Context never crosses with parent_id / user_id from sandbox. Wire-safe
// is the id only; main resolves to its authoritative Context.
message StateChanged {
  string sandbox_entity_id = 1; string state = 2;
  google.protobuf.Struct attributes = 3;    // dynamic → Struct
  optional string context_id = 4;
}

message FlowResult {
  string type = 1; optional string flow_id = 2; optional string step_id = 3;
  google.protobuf.ListValue data_schema = 4;   // serialized voluptuous → ListValue
  bool has_data_schema = 5; google.protobuf.Struct errors = 6;
  google.protobuf.Struct context = 7; /* ...title/data/reason/placeholders... */
}

// FireEvent also carries only context_id, never the full Context.
// + EntrySetup, RegisterService, FireEvent (with optional context_id),
//   StoreLoad/Save/Remove, Shutdown, RegisterEntityResult{entity_id},
//   Ready{} ...
```

- **Dynamic-field rule:** `service_data`, `target`, state `attributes`,
  `capabilities`, flow `errors`/`context` → `google.protobuf.Struct`; the
  serialized voluptuous schema (a `list[dict]`) → `google.protobuf.ListValue`.
  Everything else is an explicit field.
- **Dispatch stays string-keyed** (`type`), so adding a message = add a proto
  message + register a handler; no change to the dispatch core.
- **Context discipline (security):** `parent_id` and `user_id` are NEVER
  serialized on any outbound message from sandbox. Wire types that today
  carry `Context` carry `context_id` only. Sandbox-side caching is
  out-of-band — a small in-runtime `context_id → Context` dict main
  populates when relevant (e.g. when pushing a state-changed for an entity
  whose context originated on main). Main resolves `context_id` to its own
  Context at the dispatch site; if no such Context exists in main's
  registry, main mints one attributed to the sandbox's system user (no
  parent_id) and registers it.

## Codec & handler boundary  — DECIDED: typed handlers

`ProtobufCodec` encodes/decodes the `Frame`. For each `type`, a small registry
maps type-string → (request proto class, result proto class).

**Decision: migrate the typed handlers to consume protobuf messages directly.**
Handlers in `bridge.py`, `entry_runner.py`, `flow_runner.py`, the entity bridge,
service/event mirrors, and the store server change signature from
`Mapping[str, Any]` to their concrete proto message type (e.g.
`_handle_register_entity(msg: EntityDescription) -> RegisterEntityResult`).
Only the genuinely dynamic fields cross as Python via small
Struct↔dict / ListValue↔list helpers (`struct_to_dict` / `dict_to_struct`):
`service_data`, `target`, state `attributes`, `capabilities`,
flow `errors`/`context`, and the serialized voluptuous schema.

**Decision (2026-06-03, ratified after T1's STATUS handoff): the registry is
owned by the codec, not by `Channel.register`.** Each side builds a
`type → (request_cls, result_cls)` map from its `_proto` module and
constructs `ProtobufCodec(registry)` / `JsonCodec(registry)`. This preserves
the plan's stated safety property — the concurrency-critical `Channel` core
stays fully codec-agnostic; the codec is the only thing that knows about
proto types.

For responses to be decodable without per-call state, the proto `Frame`
envelope carries `type` on response frames too (already a field in the
envelope; populate it on the response side). The codec looks up the result
class from `frame.type` on both encode and decode.

Implications:
- `Channel.register(type, handler)` does NOT change signature; codec
  resolves the type → class pair internally.
- `SandboxEntityDescription.from_payload(dict)` and the various
  `_*_from_payload` / `_marshal_result` helpers are replaced by proto
  construction; the dataclass either wraps or is supplanted by the proto type.
- More churn across handler files, but no adapter indirection and full
  end-to-end type checking (the generated `.pyi` flows into mypy).

## Codegen & dependencies

- `.proto` lives once at `sandbox_v2/proto/sandbox_v2.proto` (source of truth).
- Generate with `grpcio-tools`/`protoc` (dev-only) into **both** mirrors
  (matching the existing "no cross-import" boundary that duplicates
  `channel.py`/`protocol.py`):
  - `homeassistant/components/sandbox_v2/_proto/sandbox_v2_pb2.py(+.pyi)`
  - `sandbox_v2/hass_client/hass_client/_proto/sandbox_v2_pb2.py(+.pyi)`
- Add a regen script `sandbox_v2/proto/generate.sh` + a note in `CLAUDE.md`
  ("regenerate after editing the .proto"). Optionally a CI/prek check that the
  checked-in generated files match a fresh generation (drift guard).
- **Runtime deps:** add `protobuf` to
  `homeassistant/components/sandbox_v2/manifest.json` `requirements` and to
  `sandbox_v2/hass_client/pyproject.toml` `dependencies`. Pin compatible with
  the `6.32.0` constraint. No `grpcio` runtime dep.

## Transport selection & handshake

- Replace the **stdout text marker** with a **`Ready` frame**: the runtime's
  first frame on the channel is `Ready{}`; the manager waits for it instead of
  scanning stdout text. stdout becomes pure channel bytes (logs already go to
  stderr). Removes the brittle "text line then binary on the same FD" mix.
- **stdio** (default): as today, over `proc.stdout`/`proc.stdin` with
  `StreamTransport`.
- **unix socket:** manager creates a socket under the config dir, passes its
  path to the subprocess; subprocess connects back; `StreamTransport` over the
  connection; `Ready` frame handshake. Main is the server.
- **websocket (DEFERRED — folds into share-states):** subprocess would dial a
  main-side WS endpoint authenticated by the **scoped sandbox token**
  (`auth.py::SANDBOX_TOKEN_SCOPES`) via the existing `--url`/`--token` args.
  This is the same connection `design-share-states.md` needs, and its auth
  endpoint is the security-sensitive boundary the auth-scoping doc flagged as
  riskiest — so it is built + security-reviewed **once**, alongside the
  subscription protocol it really exists for, not in this effort. The
  `Transport` seam is designed to accept a `WebSocketTransport` drop-in then.
- Selection: infer from `--url` scheme (`unix://…`; absent = stdio), or an
  explicit `--transport`. Lean: infer from `--url`. (`ws[s]://…` reserved for
  the deferred WS work.)

## Phased tasks (each independently testable)

- **T1 — Transport/Codec seam (no wire change yet).** Introduce `Transport`
  protocol + `StreamTransport` (length-prefixed) + `Codec` protocol +
  `JsonCodec`; refactor `Channel` to use them; move the handshake to a `Ready`
  *frame*. Net behavior identical (still JSON, still stdio) but framing is
  length-prefixed and the marker is gone. **De-risks by separating framing from
  encoding.** Existing test suites must pass unchanged (adjust only the
  handshake/marker assertions).
- **T2 — Protobuf schema + codec.** Write the `.proto`, generate + check in
  `_pb2`, add the regen script + deps, write `messages.py` adapters
  (protobuf↔dict), implement `ProtobufCodec`, switch the default codec to
  protobuf. `JsonCodec` stays for tests. Fold in #7's structured `Error` here
  (or inherit it if the fidelity batch already shipped #7 on JSON).
- **T3 — Unix socket transport.** `UnixSocketTransport` (reuses
  `StreamTransport` framing), manager-side socket creation + subprocess wiring,
  url-scheme selection, tests.
- **T4 — WebSocket transport. COMPLETELY OUT OF SCOPE** for this effort
  (re-confirmed 2026-06-03). Focus is stdio + unix socket only. The
  `Transport` Protocol that T1 already shipped is shape-compatible with a
  future `WebSocketTransport`, but no WS code, no WS deps, no WS auth
  surface lands in this batch. Lifts to the share-states work.
  (builds + security-reviews the main-side WS auth endpoint once, alongside the
  subscription protocol it's for). The `Transport` seam from T1 accepts a
  `WebSocketTransport` drop-in when that lands.
- **T5 — Cleanup.** Remove the text `READY_MARKER`, rewrite the `channel.py` /
  `protocol.py` docstrings + `OVERVIEW.md` + `CLAUDE.md`, decide whether to keep
  `JsonCodec` (lean: keep, test-only).

**This effort = T1 → T2 → T3 → T5** (stdio + unix socket, protobuf wire,
typed handlers). T4 is tracked but out of scope here.

## Risks & honest tradeoffs

- **Protobuf ROI is structural, not raw perf.** For the dynamic fields (schema,
  service_data, attrs, capabilities) protobuf-over-Struct gives ~nothing over
  JSON. The win is (a) a single typed schema as the wire's source of truth +
  versioning discipline on the known payloads, (b) smaller/faster binary on the
  high-volume `state_changed` path, (c) groundwork for non-Python clients. If
  the team doesn't value (a)/(c), JSON + length-prefixed framing + the typed
  *adapters* would deliver the multi-transport win at far lower cost — worth a
  gut-check before T2.
- **Checked-in generated code drifts.** Mitigate with the regen script + a
  prek/CI drift check.
- **Two mirrored `_pb2` copies** (no cross-import boundary). Same maintenance
  shape as today's duplicated `channel.py`/`protocol.py`; the regen script
  writes both.
- **Big-bang risk.** T1 (framing seam, JSON kept) lands and ships green before
  any protobuf, so the concurrency core is proven on the new seam before the
  encoding changes.
- **WS auth surface.** T4 adds a main-side authenticated endpoint — security-
  review territory (it's the same boundary the auth-scoping doc flagged as the
  riskiest). Keep it last and review it with the share-states work.

## Resolved decisions (2026-05-28)
- **Handler boundary → typed protobuf handlers** (no dict-adapter layer; see the
  "Codec & handler boundary" section).
- **WebSocket → deferred** to the share-states work; this effort ships stdio +
  unix socket only.
- **Protobuf wire confirmed** (over JSON+length-prefix) — the structural /
  versioning / cross-language value is wanted; ROI note kept above for honesty.

## Final phase — docs up to date
T5 already covers cleanup; treat it as this effort's docs phase
(`plan-v1-removal.md` Phase D): rewrite the wire-format docstrings in both
`channel.py`, `protocol.py`, the OVERVIEW transport section, and
`architecture.html` to describe the protobuf `Frame` + `Transport`/`Codec`
layering. Fix current-state docs; leave historical `STATUS-phase-*` intact.
