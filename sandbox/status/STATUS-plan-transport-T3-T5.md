# STATUS — plan-transport T3 + T5 (unix socket + cleanup/docs)

**One-line:** T3 + T5 shipped green — the control channel now has an opt-in
unix-socket transport alongside the default stdio (websocket rejected, not
implemented), and the wire-protocol docs describe the current
protobuf + Transport/Codec reality. Both suites green, prek + drift guard
clean. The full transport effort (T1 → T2 → T3 → T5) is **complete**; T4
(websocket) remains out of scope.

## Commits (not pushed — parent pushes)

| Phase | SHA | Subject |
|-------|-----|---------|
| T3 | `1eaa79d261e` | `sandbox_v2: unix socket transport (transport T3)` |
| T5 | `42560c6cd00` | `sandbox_v2: transport cleanup + docs (transport T5)` |

Two commits, as the brief specified. The plan file was **not** modified.

## How the manager selects stdio vs unix

A **manager-level option, defaulting to stdio** — unix is opt-in, so every
existing deployment/test keeps the unchanged stdio behavior:

```python
SandboxManager(hass, transport="stdio")  # default
SandboxManager(hass, transport="unix")   # opt-in
```

`transport` is validated at construction (`"stdio"` / `"unix"`;
`TRANSPORT_STDIO` / `TRANSPORT_UNIX` constants, unknown → `ValueError`) and
propagated to each `SandboxProcess`. `SandboxProcess._run_one` branches into
`_run_one_stdio` / `_run_one_unix`, which share a `_supervise_until_exit`
helper (ready-handshake + run-until-exit + cleanup) so the two paths differ
only in how the channel's reader/writer pair is obtained.

**The manager owns the transport, so it owns the `--url`.** `CommandFactory`
changed from `(group) -> argv` to **`(group, url) -> argv`**: the manager
computes the control-channel URL for its transport and hands it to the
factory, which puts it in `--url`. (`stdio://` for stdio; `unix://<path>`
for unix.) The five existing test command-factories were updated to the new
signature; production (`_default_command`) is unchanged apart from taking
the url.

Runtime side: the `--url` **scheme** selects the transport
(`_transport_scheme` in `hass_client/sandbox.py`):

- absent / `stdio://` → stdio (`--url` now defaults to `stdio://`, no longer
  required).
- `unix://<path>` → `asyncio.open_unix_connection(path)` → `Channel`.
- `ws://` / `wss://` → rejected (see below).

## UnixSocketTransport: not a class — StreamTransport over unix streams

There is **no `UnixSocketTransport` class**. A unix socket is just a
different byte pipe under the same length-prefixed framing, so both sides
reuse the existing `StreamTransport` (built internally by `Channel(reader,
writer)`):

- **Runtime (client):** `asyncio.open_unix_connection(path)` → the
  reader/writer pair → `Channel(..., codec=ProtobufCodec())`
  (`_open_unix_channel`).
- **Manager (server):** `asyncio.start_unix_server(accept_cb, path)`; the
  accepted `(reader, writer)` → `Channel(...)`. Main is the server.

This is exactly the "thinner approach" the brief/plan preferred ("reuses
StreamTransport framing" → the class is unnecessary). A dedicated class
would add nothing over `StreamTransport`-over-unix-streams.

## ws:// rejection behavior

`_transport_scheme` classifies `ws://` / `wss://` as `"ws"`; the runtime's
`_default_channel_factory` then raises:

```
NotImplementedError(
    "websocket transport is not implemented in this build; it is reserved
     for the share-states work — use stdio:// or unix://"
)
```

No WS code, deps, or auth surface was added — the `Transport` seam still
accepts a future `WebSocketTransport` drop-in via `Channel.from_transport`
(docstring reference only). The token still travels the CLI for forward-compat.

## Test results (exact)

- HA core: `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **191 passed, 2 warnings** (T2 was 189; +2 from the new
  `test_transport_unix.py`).
- Client: `uv run pytest sandbox_v2/hass_client/ -q` → **62 passed, 1
  warning** (T2 was 53; +9 from the new `test_transport_scheme.py`).
- `uv run prek run --files <all touched files>` → all hooks pass (ruff,
  ruff-format, codespell, prettier, mypy, pylint). prettier reformatted
  `architecture.html` once (auto-fix, now idempotent).
- Drift guard: `prek run --all-files --hook-stage manual
  sandbox-v2-proto-drift` → **Passed** (proto untouched — not regenerated).

### New tests

- `tests/components/sandbox_v2/test_transport_unix.py` (core, 2 tests):
  real subprocess unix round-trip (manager opens the socket, the real
  runtime dials back over `unix://`, `ping` round-trips, socket + tempdir
  cleaned up on shutdown — no leak); unknown-transport `ValueError`.
- `sandbox_v2/hass_client/tests/test_transport_scheme.py` (client, 9
  tests): `_transport_scheme` selection (`stdio`/`unix`/`ws` + unknown
  raises), `--url` defaults to `stdio://`, ws:// rejection raises
  `NotImplementedError`, and a hermetic `_open_unix_channel` round-trip
  against an in-process server using a typed proto `ping` handler.

### Existing tests updated

`test_manager.py`, `test_phase4_subprocess.py`, `test_phase9_shutdown.py` —
command-factory signatures moved to `(group, url)` and use the passed url
instead of the old hard-coded `ws://localhost…` literal (which would now be
rejected). `test_default_command_includes_token` passes a `stdio://` url.

## Doc files updated (T5)

- `sandbox_v2/OVERVIEW.md` — transport row, the high-level diagram label,
  and the spawn prose: protobuf `Frame` + length-prefix, Ready-frame
  handshake (no text marker), stdio + unix transports, the
  Channel/Codec/Transport layering. `--url stdio://` example.
- `sandbox_v2/architecture.html` — TOC + §5 heading, the intro paragraph,
  the SVG channel labels ("stdio protobuf", "protobuf framing"), the spawn
  command + marker prose, §5 rewritten to the three-layer split, the test
  table row, and the Phase-3 timeline `Ready`-frame note.
- `homeassistant/components/sandbox_v2/channel.py` +
  `hass_client/.../channel.py` — Codec-layer docstring (ProtobufCodec =
  production; JsonCodec = registry-free channel-core test wire).
- `homeassistant/components/sandbox_v2/protocol.py` — intro rewritten:
  typed protobuf messages, REGISTRY + `sandbox_v2.proto`, payload shapes
  are the logical contract.
- `hass_client/.../sandbox.py` — module + `SandboxRuntime` docstrings note
  the `--url`-selected transport.
- `sandbox_v2/CLAUDE.md` — **no change needed** (it does not describe the
  wire format).

## whats-changed.md boxes ticked

- `[x]` "Protobuf wire format" → T2 `360e4543300`.
- `[x]` "Pluggable transports" → T3 `1eaa79d261e`.
- `[x]` "Handlers consume typed protobuf messages" → T2 `360e4543300`.

## JsonCodec positioning

Kept (not deleted). Its docstring (both mirrors) now states it is the
**registry-free channel-core test/debug wire** — plain-JSON passthrough so
`test_channel.py` can drive the concurrency core with synthetic message
types. Production rides `ProtobufCodec`.

## Anything weird

- **The one real bug caught + fixed (unix teardown hang).** First cut hung
  forever at `server.wait_closed()` during shutdown. Root cause: when the
  runtime exits, the manager's channel read loop sees EOF and sets
  `Channel._closed = True`; the later `channel.close()` then early-returns
  **without** closing the accepted transport, so it lingers in
  `server._clients` and `wait_closed()` blocks. Fix: the unix path calls
  `server.close_clients()` (force-close lingering accepted connections)
  before `wait_closed()`. (stdio never exposed this — it has no
  `wait_closed()`.) The client round-trip test does the same in its
  teardown. Worth knowing if a `WebSocketTransport` is added later: the same
  read-EOF-then-close-is-a-noop interaction applies to any server-accepted
  transport.
- **Unix socket path length.** Linux caps `sun_path` at ~108 chars, and
  pytest/config-dir paths can be long. **Choice:** the socket lives in a
  short per-attempt `tempfile.mkdtemp(prefix="sandbox_v2_<group>_")` (e.g.
  `/tmp/sandbox_v2_built-in_xxxx/control.sock`), **not** under the config
  dir — this sidesteps the limit entirely. Did not hit the limit in
  practice. The server's `cleanup_socket` (3.13+) unlinks the socket on
  close and the whole tempdir is `rmtree`'d on the way out — confirmed no
  leaked socket file by the test.
- **Early-exit race.** `_run_one_unix` races the accept against
  `proc.wait()` so a crash-before-connect returns cleanly instead of
  hanging on the accept; the start-timeout path then surfaces
  `SandboxStartError` as usual.
- **stdout in unix mode.** The subprocess's stdout pipe is unused (frames
  ride the socket); `_supervise_until_exit(..., drain_stdout=True)` drains
  it so its buffer never fills.
- **Stale doc left intentionally (out of transport scope):** the
  architecture.html §5 "Known limitation — concurrent dispatcher" callout
  describes the one-task-per-call fix as future, but it shipped (Phase 12 /
  the inflight-semaphore dispatcher in `channel.py`). It does not mention
  the wire/marker, so it was left untouched to keep this batch scoped to the
  transport effort — flagging here for a future docs pass.

## Effort status

**T1 → T2 → T3 → T5 complete.** stdio (default) + unix-socket transports,
protobuf wire, typed handlers, current docs. **T4 (websocket) remains
out of scope** — the `Transport` seam is ready for it whenever the
share-states work lands.
