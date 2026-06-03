# STATUS — plan-transport (T1 → T2 → T3 → T5)

**One-line:** T1 (Transport/Codec seam, JSON-on-length-prefix, `Ready`
frame) shipped green; T2/T3/T5 are **not started** — T2 is an atomic
big-bang (protobuf wire + typed handlers converted in lockstep with ~69
wire-call test sites) that cannot land in safe green increments the way
T1 was designed to, so it is surfaced here for the parent to schedule as
its own focused effort rather than rammed through this session at the
risk of a broken tree or silently-weakened test assertions.

## Per-phase status

| Phase | State | Commit |
|-------|-------|--------|
| T1 — Transport/Codec seam | ✅ shipped, green | `8389f7ad96b` `sandbox_v2: Transport/Codec seam (transport T1)` |
| T2 — protobuf wire + typed handlers | ❌ not started | — (design + recipe below) |
| T3 — unix socket transport | ❌ not started (blocked on T2) | — |
| T5 — cleanup + docs | ❌ not started (blocked on T2) | — |

No `git push` was done (per brief — parent pushes). The plan file was
not modified. `whats-changed.md` boxes were **not** ticked: the three
transport boxes (Protobuf wire / Pluggable transports / typed handlers)
only flip when T2/T3 actually ship, and they did not.

## T1 — what shipped

Three-layer split of the control channel, **net behavior identical**
(still JSON, still stdio), only framing + handshake changed:

- `Channel` — unchanged dispatch core (pending-id map, inflight
  semaphore, register/call/push/close). Now speaks `Frame` objects, never
  raw bytes.
- `Codec` Protocol + `JsonCodec` — `Frame` ↔ bytes. `JsonCodec` is
  line-compatible with the old wire shape (same dict shapes, minus the
  trailing `\n` the length prefix replaces).
- `Transport` Protocol + `StreamTransport` — whole frame blobs over a
  reader/writer pair with a **4-byte big-endian length prefix**. Caps
  frame size at `MAX_FRAME_SIZE` (16 MiB) and aborts the channel on a
  larger announced length (`FrameTooLargeError`) — host-hardening against
  a compromised sandbox.
- `Frame` dataclass — unifies the three wire kinds (`call` / `push` /
  `response`) with a `FrameKind` discriminator.
- The stdout text marker `sandbox_v2:ready` is **gone**. Handshake is now
  a `MSG_READY` (`sandbox_v2/ready`) **push frame**: the runtime sends it
  as the channel's first outbound message; the manager registers a
  handler for it and flips to `running` on arrival. stdout now carries
  nothing but channel frames (logs already go to stderr).

Both mirrors (`homeassistant/components/sandbox_v2/channel.py` +
`sandbox_v2/hass_client/hass_client/channel.py`) and both `protocol.py`
were updated in lockstep. `manager._run_one` now opens the channel up
front, registers the `MSG_READY` + `on_channel_ready` handlers before
starting the reader (so the runtime's warm-load round-trip is never
dropped), then waits for the `Ready` frame.

### T1 deviations from the plan text (minor, intentional)

1. **`Channel.__init__` keeps the `(reader, writer)` signature** (plus a
   new optional `transport=` kwarg) and builds the `StreamTransport`
   internally; `Channel.from_transport(transport, …)` is the explicit
   non-stream entry point. The plan said "`Channel.__init__` takes a
   `Transport` + `Codec` instead of a raw reader/writer." Keeping the
   stream constructor let **every existing test + `manager`/`sandbox`
   call site stay byte-for-byte unchanged** (the brief's "existing test
   suites must pass unchanged except handshake/marker assertions"). The
   `Transport` seam is fully real — `Channel` delegates all I/O to
   `self._transport`; `from_transport` is the WebSocketTransport drop-in
   path, and it is exercised by a new `test_from_transport_round_trips`
   (in-memory queue transport) so it is not dead code.
2. **`READY_MARKER` was removed in T1, not deferred to T5.** The plan
   lists marker removal under T5, but leaving a dead constant + dead
   stdout-scan code through T2/T3 was worse than removing it now. T5's
   marker work is therefore docs-only (OVERVIEW/architecture.html still
   describe the old marker — see "T5 remaining").

### T1 verification

- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → **183 passed**
- `uv run pytest sandbox_v2/hass_client/ -q` → **53 passed**
- `uv run prek run --files <9 touched files>` → all hooks pass (ruff,
  ruff-format, codespell, mypy, pylint).
- `grep -rn READY_MARKER` over `sandbox_v2/` + `homeassistant/` → only
  **docs** remain (`OVERVIEW.md`, `architecture.html`, historical
  `STATUS-phase-3.md`, `plan.md`) — code is clean. T5 cleans the docs.
- `grep -rn WebSocketTransport …` → empty (T4 correctly not introduced).

## Toolchain gate for T2 — CLEARED (recipe verified)

Core has **no `protoc` and no `grpcio-tools`** (and the client venv had
no `protobuf` at all). `protobuf` is pinned to **6.32.0** in
`homeassistant/package_constraints.txt`. Installing `grpcio-tools`
directly into the **main** venv bumps `protobuf` → 6.33.x and `grpcio`
→ 1.81 (breaks the pin) — **do not do that** (the main venv was repaired
back to `protobuf==6.32.0` / `grpcio==1.80.0`).

Verified working recipe — generate in an **isolated** venv pinned to the
runtime, so the main/client venvs are never polluted:

```bash
uv venv /tmp/protogen --python 3.14
uv pip install --python /tmp/protogen "protobuf==6.32.0" grpcio-tools mypy-protobuf
# resolver picks grpcio-tools==1.80.0 (compatible with protobuf 6.32.0)
/tmp/protogen/bin/python -m grpc_tools.protoc \
  -I sandbox_v2/proto \
  --python_out=<dest> --pyi_out=<dest> \
  sandbox_v2/proto/sandbox_v2.proto
```

`grpcio-tools==1.80.0` emits gencode whose runtime gate is
`ValidateProtobufRuntimeVersion(PUBLIC, 6, 31, 1, …)` — i.e. it requires
protobuf **≥ 6.31.1**, which the pinned **6.32.0 satisfies**. Confirmed:
the generated `_pb2.py` imports + serializes cleanly under the main
venv's protobuf 6.32.0. **So T2's checked-in gencode is runtime-safe.**

The regen script (`sandbox_v2/proto/generate.sh` per plan) should
bootstrap this isolated venv (not the project venv) and write both
mirrors. The prek/CI drift guard must run the same isolated-venv
generation then `git diff --exit-code` the two `_pb2`/`_pb2.pyi` paths;
because grpcio-tools isn't a project dep, the hook needs to create the
throwaway venv itself (or be a manual/optional CI lane) — note this when
wiring it so it degrades gracefully where grpcio-tools is absent.

## T2 — resolved design (the real handoff)

The plan's "Codec & handler boundary — DECIDED: typed handlers" leaves
one thing implicit that has to be nailed before coding: **a stateless
codec can't type a `response`'s `result` bytes**, because responses don't
obviously carry the message `type`. Resolution:

1. **Carry `type` on the response frame too.** The proto `Frame`
   envelope already has `type` as field 2 (always set) with a
   `oneof body { request | response }`. Populate `type` on response
   frames (the channel knows it at dispatch time). Then the codec can
   look up the result class from `frame.type` on **both** encode and
   decode — no per-call state needed. The `Frame` dataclass already has
   a `type` field; `_run_call_handler` just needs to pass the request's
   `type` into the response `Frame` (today it builds `ok_response`
   without `type`). `JsonCodec` may keep omitting `type` on the wire for
   responses (it infers kind from key presence); `ProtobufCodec` writes
   it.
2. **The request/result class pair lives in the *codec's* registry, not
   `Channel.register`.** This is a deliberate refinement of the plan's
   "`Channel.register` gains the proto class pair": keeping the pairing
   in the codec keeps the concurrency-critical `Channel` core fully
   codec-agnostic — exactly the plan's stated safety property ("the
   concurrency-critical core doesn't move"). Each side builds a
   `type → (request_cls, result_cls)` registry from its `_proto` module
   and constructs `ProtobufCodec(registry)` / `JsonCodec(registry)`. **This
   is a deviation worth the parent's explicit ✅ before T2 coding.**
3. **Both codecs become message-aware and hand handlers proto messages.**
   `ProtobufCodec` (de)serializes via protobuf; `JsonCodec` becomes a
   "proto-as-JSON" codec (`json_format.MessageToDict` /`ParseDict`) so it
   stays a human-readable debugging/test wire for the *same* typed
   messages. Handlers always receive a concrete proto message — no dict
   path (locked decision honored).
4. **Dynamic fields** (`service_data`, `target`, state `attributes`,
   `capabilities`, flow `errors`/`context`, and the serialized voluptuous
   schema → `ListValue`) cross via small `struct_to_dict` /
   `dict_to_struct` / `listvalue_to_list` helpers. Everything else is an
   explicit proto field.
5. **`Error` / `InvalidError` messages** carry fidelity #7's structured
   `vol.Invalid` data natively (already shipped on JSON via
   `error_data_for` / `_rebuild_invalid`; T2 keeps identical semantics on
   the typed `Error` message — `message`, `type`, `repeated InvalidError`).

### Proposed `.proto` (refined from the plan §"Protobuf schema")

Source of truth: `sandbox_v2/proto/sandbox_v2.proto`. Envelope + `Error`
exactly as the plan. Typed bodies needed (one per wire `type`):

- `EntrySetup` (entry_setup) → `EntrySetupResult{ok, reason}`
- `EntryUnload{entry_id}` (entry_unload) → `EntryUnloadResult{ok}`
- `CallService` (call_service) → `CallServiceResult{has_response, response:Struct}`
- `Shutdown{}` (shutdown) → `ShutdownResult{ok, unloaded, restore_state:Struct/bytes}`
- `Ping{}` (ping) → `PingResult{pong}`
- `Ready{}` (ready, push)
- `FlowInit`/`FlowStep`/`FlowAbort` → `FlowResult` (plan has the field list)
- `EntityDescription` (register_entity) → `RegisterEntityResult{entity_id}`
- `UnregisterEntity{sandbox_entity_id}` → `UnregisterEntityResult{ok}`
- `StateChanged` (state_changed, push)
- `RegisterService`/`UnregisterService` → results
- `FireEvent` (fire_event, push)
- `StoreLoad{key}` → `StoreLoadResult{has_data, data:Struct}`,
  `StoreSave{key, data:Struct}` → `{ok}`, `StoreRemove{key}` → `{ok}`
- `DeviceInfo` (nested in `EntityDescription`) — all known `DeviceInfo`
  TypedDict keys as explicit fields; `identifiers`/`connections` as
  `repeated` pairs, `via_device` as a pair, `entry_type` as string.

### Why T2 is a big-bang (not landable in green increments here)

Flipping the default codec to protobuf + switching every handler to typed
messages must happen **atomically** — the moment handlers expect proto
messages, every caller (production *and* tests) must pass/return proto
messages. Surface to convert in one commit:

- **~20 handlers** across both sides: HA `bridge.py` (register/unregister
  entity, state_changed, register/unregister service, fire_event,
  store_load/save/remove), client `entry_runner.py` (entry_setup/unload,
  call_service), `flow_runner.py` (`_marshal_result` + 3 handlers),
  `entity_bridge.py`, `service_mirror.py`, `event_mirror.py`,
  `sandbox_bridge.py`, plus `schema_bridge.py` (both sides).
- **~69 `.call(`/`.push(` test sites** across `test_bridge.py` (18),
  `test_store.py` (13), `test_channel.py` (11 — these stay JSON), the
  client `test_flow_runner`/`test_entry_runner`/`test_entity_bridge`/
  `test_service_mirror`/`test_event_mirror`/`test_sandbox_bridge`/
  `test_shutdown`, and the HA `test_phase13/14/19`. Each that drives a
  typed message must build/assert a proto message instead of a dict — a
  faithful but high-volume mechanical translation where a careless edit
  silently weakens an assertion.
- **New modules** per side: `_proto/sandbox_v2_pb2.py(+.pyi)`,
  `messages.py` (typed adapters — kept in sync across the boundary like
  `channel.py`/`protocol.py`), `codec_protobuf.py` (or fold into
  `channel.py`), the registry, struct helpers.
- **Deps:** `protobuf` → client `pyproject.toml` `dependencies` + HA
  `manifest.json` `requirements` (the latter triggers hassfest
  `requirements_all.txt` regeneration — a core-side change to validate
  carefully; **do not** touch `IGNORE_INTEGRATIONS_WITH_ERRORS`).
  `grpcio-tools`/`mypy-protobuf` → a **dev** requirements file only.

This is exactly the work; it's just too large + atomic to land safely in
the remainder of this session without risking the green tree T1
established.

## T3 — shape (blocked on T2)

`UnixSocketTransport` is thin: it reuses `StreamTransport`'s
length-prefixed framing over the `(reader, writer)` from
`asyncio.open_unix_connection` (subprocess) / `start_unix_server` accept
(manager). Manager creates a socket under the config dir, passes the path
to the subprocess, infers transport from the `--url` scheme
(`unix://…` vs absent = stdio; `ws[s]://…` reserved for deferred WS).
`Channel(reader, writer)` already covers it — the `Transport` Protocol is
in place. Mostly manager wiring + new tests.

## T5 — remaining (blocked on T2; some already done by T1)

- ✅ Already removed in T1: the `READY_MARKER` constant + stdout scan code.
- ⬜ Docs still describing the old wire/marker: `OVERVIEW.md` "Wire
  protocol"/"Channel" sections, `architecture.html` wire-format + runtime
  diagram, and the `channel.py`/`protocol.py` docstrings (T1 already
  rewrote the channel docstrings to describe the layering; revisit after
  T2 to mention protobuf as the default codec).
- ⬜ Keep `JsonCodec` as test-only (lean: keep) and say so in its docstring
  (T1 docstring already calls it the test/debug default — update once
  protobuf is the production default).
- ⬜ Tick the 3 `whats-changed.md` transport boxes with SHAs.

## Anything weird

- **Two mirrored generated `_pb2` copies** will exist (one per side,
  matching the existing `channel.py`/`protocol.py` no-cross-import
  boundary). The regen script must write both; the drift guard must check
  both. No drift today (none generated yet).
- The **`messages.py` adapter modules** become a third pair that must be
  kept in sync by hand across the boundary, like `channel.py`/`protocol.py`.
- **No deviation from the typed-handler decision** was made (T2 not
  started). The one design refinement to confirm: **codec owns the
  request/result class registry** rather than `Channel.register` (keeps
  the dispatch core codec-agnostic — see T2 design point 2).

## Recommendation

T1 is a clean, reviewable, independently-green commit — safe to push as
its own PR or to sit at the head of the branch while T2 is scheduled.
T2 should be its own focused session/PR using the verified codegen recipe
and the resolved design above; T3 + T5 are small fast-follows once T2's
seam is in protobuf.
