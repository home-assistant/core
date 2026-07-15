"""Stable-URL, credential-free-in-spirit RTSP front-door for REMOTE sessions.

Companion to `viewing_front_door.py` (LOCAL), built for the analogous but
structurally different problem on the REMOTE (cloud-relay) path, as part of
the same HA-Core-submission-prep go2rtc-native-registration-leak fix
(2026-07-14).

Problem: HA-core's own built-in go2rtc integration registers whatever
`camera.stream_source()` currently returns on every WebRTC offer, purely
additively — no removal API, dedup only on an exact URL-string match. A
`stream_source()` URL that changes leaks a new dead go2rtc entry every time.

REMOTE is structurally different from LOCAL, which is why this is a
separate module rather than an extension of `viewing_front_door.py`:

  * REMOTE has NO Digest user/password pair at all. Its "credential" is a
    single opaque `{hash}` baked directly into the URL PATH (not `user:pass@`
    userinfo): Bosch's `PUT /connection` response yields a path like
    `/{hash}/rtsp_tunnel?inst=...`, which `live_connection.py` already runs
    through `tls_proxy.py`'s TLS-terminating proxy (same function LOCAL
    uses, just pointed at the Bosch cloud relay host) to produce
    `rtsp://127.0.0.1:{proxy_port}/{hash}/rtsp_tunnel?inst=...` — the hash
    is still embedded in THIS proxied URL's path, just now behind
    127.0.0.1 instead of the real cloud host.
  * REMOTE's session lifetime is ~1hr (`maxSessionDuration`) and
    `session_renewal.py`'s `remote_session_terminator` proactively tears
    the WHOLE session down before that boundary rather than renewing
    mid-session (see that function's own docstring for why: renewing would
    force a 30s+ pre-warm window mid-stream). So within one REMOTE session
    the hash and inner proxy port are STABLE — the only churn is at session
    boundaries (initial connect, ~hourly re-open, any reconnect-after-drop),
    each minting a fresh hash + a fresh ephemeral inner proxy port. Lower
    frequency than LOCAL's ~15s Digest-cred rotation, but still an
    unbounded "one new go2rtc entry per hour forever" leak worth fixing.

Because there is no Digest challenge/response for REMOTE (no
`Authorization:` header to inject — the hash IS the credential, and it's
already baked into the path forwarded to the inner TLS proxy), this module
does NOT reuse `frigate_endpoint.py`'s `_Relay` — that class exists purely
to conduct a Digest auth dance and has no `Authorization`-less code path
that would make sense here. Instead, `_PathRewriteRelay` below implements a
simpler mechanism: the front-door publishes a STABLE path (no hash — same
"rtsp_tunnel?inst=..." shape `viewing_front_door.py` publishes for LOCAL),
and on every incoming RTSP request `_PathRewriteRelay` rewrites the
request-line URI to substitute the CURRENT session's actual hash-bearing
path (resolved fresh per client CONNECT, via `remote_resolve_inner`, the
same "read live state fresh, never call try_live_connection()" contract
`viewing_resolve_inner` already established for LOCAL) before forwarding to
the inner TLS proxy on `127.0.0.1:{inner_port}`. A session-boundary
reconnect that mints a new hash is transparently handled — the NEXT client
(re)connect picks up the new path; there is no need to handle an
in-flight hash rotation mid-connection, since a session boundary always
tears the old inner TLS proxy port down too (the old TCP connection to it
dies on its own).

`_CameraServer`/`FrontDoorRunner` (`frigate_endpoint.py`) are still reused
here via the `relay_factory` hook added to `FrontDoorRunner.start_server`
specifically for this module — the listener lifecycle, sticky-port retry,
IP-allowlist, and connection-cap machinery are all identical to the LOCAL
viewing front-door's needs, only the per-connection relay differs.

Separate coordinator state (`_remote_viewing_front_door_runner` /
`_remote_viewing_sticky_port`) from LOCAL's `_viewing_front_door_runner` /
`_viewing_sticky_port` — considered and REJECTED sharing them: a camera's
`_connection_type` is LOCAL xor REMOTE per live session, so at first glance
sharing looked safe (guidance in the originating task explicitly flagged
this as worth checking). But a LOCAL→REMOTE or REMOTE→LOCAL transition
that does NOT go through `_tear_down_live_stream` first — e.g.
`session_renewal.promote_to_local`'s REMOTE→LOCAL live promotion, which
calls `try_live_connection(is_renewal=True)` directly, not a teardown+
reopen — would leave the OLD front-door's listener still bound under a
SHARED runner. Both `start_viewing_front_door`/`start_remote_...` short-
circuit to "reuse the already-bound listener" whenever
`runner.has_server(cam_id)` is true (the bug-hunt-driven optimization from
the LOCAL front-door's own initial commit, avoiding needless rebinds on
routine renewals) — with a shared runner that reuse check can't tell
"bound, but with the WRONG relay type for the NEW connection type" apart
from "bound, and fine to reuse", silently wiring a Digest-auth relay to a
REMOTE resolve function (or vice versa) after a cross-type promotion.
Separate runners make that failure mode structurally impossible: each
runner's own resolve function already rejects the wrong `_connection_type`
(returns None → 503) exactly as it did before this feature existed, so a
stale listener from the OTHER type just quietly 503s any leftover client
until its owning module's teardown call catches up — an unchanged
degradation mode, not a new bug this feature introduces.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from .frigate_endpoint import (
    AUTH_NONE,
    FrontDoorConfig,
    FrontDoorRunner,
    Relay,
    _close_writer,
    _rewrite_request_uri,
    content_length,
    find_rtsp_message_end,
)

_LOGGER = logging.getLogger(__name__)

# Mirrors frigate_endpoint.py's _INNER_CONNECT_TIMEOUT / _MAX_HEAD_BYTES —
# same inner-proxy-connect and request-head-size bounds, just not shared
# constants across modules (frigate_endpoint.py's are module-private).
_INNER_CONNECT_TIMEOUT = 10.0
_MAX_HEAD_BYTES = 64 * 1024


@dataclass(frozen=True)
class RemoteTarget:
    """What `remote_resolve_inner` returns.

    The live inner TLS-proxy port plus the CURRENT session's hash-bearing
    path+query (e.g.
    ``/{hash}/rtsp_tunnel?inst=1&enableaudio=1&fmtp=1&maxSessionDuration=3600``).
    """

    port: int
    path: str


class _PathRewriteRelay:
    """Relays one downstream client <-> inner-proxy connection, rewriting every forwarded RTSP request's URI to the CURRENT session's hash path.

    No credential dance at all — unlike `frigate_endpoint._Relay`, there is
    no `Authorization:` challenge/response here. `target.path` already
    carries everything the inner TLS proxy needs (the hash is baked into
    the path itself); rewriting the request-line URI to
    ``rtsp://127.0.0.1:{target.port}{target.path}`` before every forward is
    the entire mechanism.
    """

    def __init__(
        self,
        cam_id: str,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target: RemoteTarget,
        first_request: bytes,
    ) -> None:
        self._cam = cam_id[:8]
        self._cr = client_reader
        self._cw = client_writer
        self._target = target
        self._first = first_request
        self._ir: asyncio.StreamReader | None = None
        self._iw: asyncio.StreamWriter | None = None

    def _rewritten_uri(self) -> str:
        return f"rtsp://127.0.0.1:{self._target.port}{self._target.path}"

    async def run(self) -> None:
        """Connect to the inner proxy, forward the first request rewritten.

        Then pipe both directions.
        """
        ir, iw = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", self._target.port),
            timeout=_INNER_CONNECT_TIMEOUT,
        )
        self._ir, self._iw = ir, iw
        try:
            iw.write(_rewrite_request_uri(self._first, self._rewritten_uri()))
            await iw.drain()
            await asyncio.gather(
                self._pipe_client_to_inner(),
                self._pipe_inner_to_client(),
            )
        finally:
            for w in (iw, self._cw):
                if not w.is_closing():
                    await _close_writer(w)

    async def _pipe_client_to_inner(self) -> None:
        """Forward client->inner, rewriting the URI of every RTSP request."""
        assert self._iw is not None
        buf = b""
        try:
            while True:
                chunk = await self._cr.read(65536)
                if not chunk:
                    break
                buf += chunk
                buf = await self._drain_requests(buf)
        except asyncio.IncompleteReadError, ConnectionError, OSError:
            pass
        finally:
            if not self._iw.is_closing():
                await _close_writer(self._iw)

    async def _drain_requests(self, buf: bytes) -> bytes:
        """Emit every complete request in ``buf`` (URI rewritten), return the unparsed tail.

        Mirrors `_Relay._drain_requests`'s framing — interleaved RTP/RTCP
        binary frames (`$`) are forwarded raw, never parsed as RTSP.
        """
        assert self._iw is not None
        while buf:
            if buf[:1] == b"$":
                self._iw.write(buf)
                await self._iw.drain()
                return b""
            end = find_rtsp_message_end(buf)
            if end < 0:
                if len(buf) > _MAX_HEAD_BYTES:
                    # Not RTSP and not interleaved — forward raw to avoid a stall.
                    self._iw.write(buf)
                    await self._iw.drain()
                    return b""
                return buf
            req, buf = buf[:end], buf[end:]
            body = content_length(req)
            if body:
                if len(buf) < body:
                    return req + buf  # body incomplete — wait for more
                req, buf = req + buf[:body], buf[body:]
            self._iw.write(_rewrite_request_uri(req, self._rewritten_uri()))
            await self._iw.drain()
        return b""

    async def _pipe_inner_to_client(self) -> None:
        """Forward inner->client verbatim (RTP frames, responses).

        Nothing in a response needs rewriting.
        """
        assert self._ir is not None
        try:
            while True:
                chunk = await self._ir.read(65536)
                if not chunk:
                    break
                self._cw.write(chunk)
                await self._cw.drain()
        except ConnectionError, OSError:
            pass
        finally:
            if not self._cw.is_closing():
                await _close_writer(self._cw)


def _remote_relay_factory(
    cam_id: str,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target: Any,
    first_request: bytes,
) -> Relay:
    return _PathRewriteRelay(
        cam_id, client_reader, client_writer, target, first_request
    )


async def remote_resolve_inner(coordinator: Any, cam_id: str) -> RemoteTarget | None:
    """Return the current inner TLS-proxy port + hash-bearing path, or None.

    Deliberately does NOT open a session itself (same "reuse, don't open"
    contract as `viewing_resolve_inner` — see that function's docstring):
    the main viewing path (`live_connection.py`) always already has an
    active REMOTE session open by the time this front-door is running, and
    calling `try_live_connection()` here would mint a fresh hash + inner
    proxy port on every resolve, defeating the whole point of a stable
    published URL.

    Returns None (front-door replies 503, client retries) when there is no
    active REMOTE session for this camera — the session was torn down,
    promoted to LOCAL (`session_renewal.promote_to_local`), or the inner
    TLS proxy/path haven't been recorded yet.
    """
    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "REMOTE":
        return None
    port = coordinator.tls_proxy_ports.get(cam_id)
    path = live.get("_remote_path")
    if not (port and path):
        return None
    return RemoteTarget(port=port, path=str(path))


async def start_remote_viewing_front_door(
    coordinator: Any,
    cam_id: str,
    *,
    inst: int,
    audio_param: str,
    max_session_duration: int,
) -> str | None:
    """Start (or reuse) the stable-URL REMOTE viewing front-door for `cam_id`.

    Returns the stable-port, hash-free RTSP URL to publish via
    `stream_source()`, or None if the listener could not be bound at all
    (caller should fall back to the raw hash-bearing proxied URL so
    streaming still works, just without the stable-URL benefit).

    Mirrors `viewing_front_door.start_viewing_front_door`'s "genuinely
    reuse an already-bound listener" behaviour (same bug-hunt rationale:
    `remote_resolve_inner` reads the fresh inner port/path per client
    (re)connect, so a routine call for an already-running listener must not
    restart it — that would needlessly ECONNREFUSE a client racing the
    close->rebind gap for zero benefit).
    """
    if coordinator.remote_viewing_front_door_runner is None:
        coordinator.remote_viewing_front_door_runner = FrontDoorRunner()
    runner = coordinator.remote_viewing_front_door_runner
    if runner.has_server(cam_id):
        return (
            f"rtsp://127.0.0.1:{runner.port(cam_id)}/rtsp_tunnel"
            f"?inst={inst}{audio_param}&fmtp=1&maxSessionDuration={max_session_duration}"
        )
    config = FrontDoorConfig(bind_host="127.0.0.1", auth_mode=AUTH_NONE)
    try:
        port = await runner.start_server(
            cam_id,
            config,
            lambda cid: remote_resolve_inner(coordinator, cid),
            preferred_port=coordinator.remote_viewing_sticky_port.get(cam_id, 0),
            relay_factory=_remote_relay_factory,
        )
    except OSError as err:
        # Sticky port taken (e.g. after a reload) — retry on an ephemeral
        # port. Mirrors viewing_front_door.py's own two-tier OSError
        # handling exactly.
        _LOGGER.warning(
            "REMOTE viewing front-door %s: bind on sticky port failed (%s) — using ephemeral",
            cam_id[:8],
            err,
        )
        coordinator.remote_viewing_sticky_port.pop(cam_id, None)
        try:
            port = await runner.start_server(
                cam_id,
                config,
                lambda cid: remote_resolve_inner(coordinator, cid),
                relay_factory=_remote_relay_factory,
            )
        except OSError as err2:
            # The first OSError assumed "port taken", but an ephemeral
            # (port=0) bind still uses `config.bind_host` — if THAT is the
            # problem the retry fails with the same error, so it must be
            # caught separately rather than left to propagate.
            _LOGGER.error(
                "REMOTE viewing front-door %s: could not bind even an ephemeral port (%s)",
                cam_id[:8],
                err2,
            )
            return None
    coordinator.remote_viewing_sticky_port[cam_id] = port
    return (
        f"rtsp://127.0.0.1:{port}/rtsp_tunnel?inst={inst}{audio_param}"
        f"&fmtp=1&maxSessionDuration={max_session_duration}"
    )


async def stop_remote_viewing_front_door(coordinator: Any, cam_id: str) -> None:
    """Stop the REMOTE viewing front-door listener for `cam_id`, if running."""
    if coordinator.remote_viewing_front_door_runner is not None:
        coordinator.remote_viewing_front_door_runner.stop_server(cam_id)
