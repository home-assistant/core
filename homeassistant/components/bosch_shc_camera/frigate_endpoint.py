"""Always-on, credential-free RTSP front-door for external recorders (Frigate/BlueIris).

Problem (HA#37, MattSharp + forum requests): the per-camera TLS proxy
(``tls_proxy.py``) only binds its TCP port while a livestream session is open,
and the URL it exposes carries inline Digest credentials that rotate roughly
hourly. An external recorder (Frigate, BlueIris, go2rtc add-on) polls the RTSP
URL on its own schedule, so whenever the livestream is off — the default, and
the state after every HA restart, privacy-credential rotation or 60-minute
session renewal — the recorder gets "Connection refused" or a 401.

This module is the HA analogue of the ioBroker adapter's ``lazy_stream.ts`` +
``rtsp_auth.ts`` (forum #84538). It adds, per camera, an always-listening
front-door bound to a stable port that:

  * stays bound regardless of Bosch session state (no more ECONNREFUSED),
  * opens the Bosch session + inner TLS proxy lazily on the first client
    connection (``resolve_inner`` callback) and releases it after an idle
    linger, so the 3-shared-session budget is respected,
  * speaks RTSP and performs the Digest auth dance itself, so clients receive a
    **credential-free** URL (``rtsp://host:port/high`` — no ``user:pass@``),
  * optionally restricts access by client IP (allowlist) and/or a shared
    secret (path-token or RTSP Basic-auth), all opt-in via the integration
    options. Default bind is ``127.0.0.1`` (localhost-only).

Architecture: the front-door byte-relays to the existing inner TLS proxy
(``127.0.0.1:<inner-port>``) which keeps its proven TLS + SETUP→TCP-interleave
behaviour untouched. Only the Digest ``Authorization:`` header is injected by
the front-door, using the live session's rotating creds — so the camera-facing
RTSP URIs are forwarded verbatim (same SDP/control-URL behaviour as the
direct-FFmpeg path, which is what makes this safe on a LAN bind).

Runs directly on HA's event loop: the listeners are asyncio ``start_server``
sockets and each relay is an asyncio task, all non-blocking. ``resolve_inner``
is awaited on the same loop (no thread, no cross-loop bridging).
"""

import asyncio
import base64
from collections.abc import Callable, Coroutine
import contextlib
from dataclasses import dataclass, field
import hmac
import ipaddress
import logging
import socket
from typing import Any, Protocol, TypeVar
from urllib.parse import quote as _urlquote

from bosch_shc_camera_client.auth_utils import (
    _build_digest_header,
    _parse_digest_challenge,
)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

# Auth modes (mirrored in const.py CONF defaults + the options flow selector).
AUTH_NONE = "none"
AUTH_PATH_TOKEN = "path_token"  # auth-mode name, not a credential
AUTH_BASIC = "basic"

# Quality selectors → Bosch RTSP ``inst`` query value. High = main encoder
# (inst=1), Low = sub-stream (inst=2). One front-door serves both: each
# published URL carries the matching ``inst`` and is forwarded verbatim.
QUALITY_HIGH = "high"
QUALITY_LOW = "low"
_QUALITY_INST = {QUALITY_HIGH: 1, QUALITY_LOW: 2}

# Max time to wait for the inner proxy TCP connect before dropping the client.
_INNER_CONNECT_TIMEOUT = 10.0
# Max time to wait for resolve_inner (opening a Bosch session can pre-warm ~25s).
_RESOLVE_TIMEOUT = 40.0
# Max time to wait for one inner RTSP response during the auth dance.
_AUTH_READ_TIMEOUT = 30.0
# Max bytes for a single RTSP message head (guards against a non-RTSP flood).
_MAX_HEAD_BYTES = 64 * 1024
# Max concurrent clients per camera front-door (guards against connection floods).
_MAX_CONCURRENT_CLIENTS = 8


@dataclass(frozen=True)
class InnerTarget:
    """What ``resolve_inner`` returns: the live inner proxy + current creds."""

    port: int
    digest_user: str
    digest_password: str


# resolve_inner(cam_id) -> awaitable[target | None]; None = camera currently
# unreachable / no session → the front-door drops the client cleanly so the
# recorder retries later. Runs on the HA event loop (bridged thread-safely).
#
# The return type is deliberately `Any` (not `InnerTarget | None`) so this
# same generic `_CameraServer`/`FrontDoorRunner` machinery can host a
# DIFFERENT resolve+relay pair for a mechanism that has no Digest
# challenge/response at all — see `remote_viewing_front_door.py`'s
# `RemoteTarget`/`remote_resolve_inner`, built for REMOTE sessions (whose
# "credential" is an opaque hash baked into the URL path, not a user:pass
# pair) via the `relay_factory` hook on `FrontDoorRunner.start_server`
# below. Every concrete resolve function still declares its own precise
# return type (e.g. `InnerTarget | None`) at its definition site — `Any`
# here only widens what this shared plumbing itself is willing to carry
# through unexamined between resolve and relay-factory.
ResolveInner = Callable[[str], Coroutine[Any, Any, Any]]


class Relay(Protocol):
    """What a `RelayFactory` must produce: something with an async `run()`.

    `_Relay` (Digest-injecting, below) and `remote_viewing_front_door.py`'s
    `_PathRewriteRelay` (URI path-rewriting, no credential dance at all —
    REMOTE has no Authorization challenge to answer) both satisfy this
    structurally; `_CameraServer._serve` only ever calls `.run()`.
    """

    async def run(self) -> None: ...


# relay_factory(cam_id, client_reader, client_writer, target, first_request)
# -> a Relay. `target` is typed `Any` for the same reason `ResolveInner`'s
# return type is `Any` above — each factory pairs with a matching
# resolve_inner and casts/uses `target`'s concrete attributes itself.
RelayFactory = Callable[
    [str, "asyncio.StreamReader", "asyncio.StreamWriter", Any, bytes], Relay
]


@dataclass
class FrontDoorConfig:
    """Per-integration front-door settings (from the options flow)."""

    bind_host: str = "127.0.0.1"
    # Empty = allow any client IP. Entries may be plain IPs or CIDR networks.
    ip_allowlist: frozenset[str] = field(default_factory=frozenset)
    auth_mode: str = AUTH_NONE
    # Shared secret: the path segment for AUTH_PATH_TOKEN, the password for
    # AUTH_BASIC. Empty disables that gate even if the mode is set.
    token: str = ""
    basic_user: str = "frigate"
    # Zero-client linger before signalling idle (caller tears the session down).
    idle_timeout: float = 60.0
    # Max simultaneous recorder clients per camera (anti-flood guard).
    max_connections: int = 8


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (exported for unit tests) — ported from ioBroker rtsp_auth.ts.
# ─────────────────────────────────────────────────────────────────────────────


def find_rtsp_message_end(buf: bytes) -> int:
    """Return the offset right after ``\\r\\n\\r\\n``, or -1 if not present."""
    i = buf.find(b"\r\n\r\n")
    return i + 4 if i >= 0 else -1


def parse_request_start_line(buf: bytes) -> tuple[str, str] | None:
    """Parse ``METHOD uri RTSP/1.x`` from the first line. None on parse error."""
    eol = buf.find(b"\r\n")
    first = (buf[:eol] if eol >= 0 else buf).decode("utf-8", errors="replace")
    parts = first.split()
    if len(parts) >= 3 and parts[2].upper().startswith("RTSP/") and parts[0].isupper():
        return parts[0], parts[1]
    return None


def parse_response_status(buf: bytes) -> int | None:
    """Parse the numeric code from an ``RTSP/1.0 NNN PHRASE`` start line."""
    eol = buf.find(b"\r\n")
    first = (buf[:eol] if eol >= 0 else buf).decode("utf-8", errors="replace")
    parts = first.split()
    if len(parts) >= 2 and parts[0].upper().startswith("RTSP/") and parts[1].isdigit():
        return int(parts[1])
    return None


def extract_header(buf: bytes, name: str) -> str | None:
    """Return the first value of header ``name`` (case-insensitive), or None."""
    lname = name.lower()
    for line in buf.decode("utf-8", errors="replace").split("\r\n"):
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == lname:
            return value.strip()
    return None


def has_authorization_header(buf: bytes) -> bool:
    """True if the request headers contain an ``Authorization:`` line."""
    return extract_header(buf, "Authorization") is not None


def content_length(buf: bytes) -> int:
    """Parse ``Content-Length`` (0 when absent or unparseable)."""
    raw = extract_header(buf, "Content-Length")
    if raw and raw.isdigit():
        return int(raw)
    return 0


def inject_auth_header(request: bytes, auth_value: str) -> bytes:
    """Insert ``Authorization: <value>`` before the blank line ending the head.

    Any existing ``Authorization:`` line is dropped first so a client-supplied
    (gate) credential never reaches the camera alongside our injected Digest.
    Caller has verified the buffer ends with ``\\r\\n\\r\\n``.
    """
    sep = request.find(b"\r\n\r\n")
    if sep < 0:
        return request
    head = request[:sep].decode("utf-8", errors="replace")
    tail = request[sep:]
    kept = [
        ln
        for ln in head.split("\r\n")
        if not ln.split(":", 1)[0].strip().lower() == "authorization"
    ]
    kept.append(f"Authorization: {auth_value}")
    return ("\r\n".join(kept)).encode("utf-8") + tail


def ip_allowed(peer_ip: str, allowlist: frozenset[str]) -> bool:
    """True if ``peer_ip`` is permitted. Empty allowlist = allow all."""
    if not allowlist:
        return True
    try:
        ip = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    # A dual-stack (0.0.0.0) bind reports an IPv4 client as an IPv4-mapped IPv6
    # address (``::ffff:192.0.2.5``). Match against the real IPv4 too, so an
    # IPv4 allowlist entry still applies. (forum/verify-agent finding 2026-06-24)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if ip in ipaddress.ip_network(entry, strict=False):
                    return True
            elif ip == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def split_path_token(uri: str, token: str) -> tuple[bool, str]:
    """Validate + strip a leading ``/<token>`` path segment from ``uri``.

    Returns ``(ok, rewritten_uri)``. ``ok`` is False when the token is required
    but missing/wrong. The rewritten URI has the token segment removed so the
    camera sees the canonical path (e.g. ``rtsp://h:p/tok/high`` → ``…/high``).
    """
    if not token:
        return True, uri
    # Work on the path portion only; preserve scheme://host and ?query.
    scheme_sep = uri.find("://")
    prefix = ""
    rest = uri
    if scheme_sep >= 0:
        slash = uri.find("/", scheme_sep + 3)
        if slash < 0:
            return False, uri
        prefix = uri[:slash]
        rest = uri[slash:]
    query = ""
    qpos = rest.find("?")
    if qpos >= 0:
        query = rest[qpos:]
        rest = rest[:qpos]
    segments = [s for s in rest.split("/") if s != ""]
    if not segments or not hmac.compare_digest(segments[0], token):
        return False, uri
    remainder = "/" + "/".join(segments[1:])
    return True, f"{prefix}{remainder}{query}"


def check_basic_auth(buf: bytes, user: str, password: str) -> bool:
    """True if the request carries a matching ``Authorization: Basic`` header."""
    value = extract_header(buf, "Authorization")
    if not value:
        return False
    scheme, _, b64 = value.partition(" ")
    if scheme.strip().lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(b64.strip(), validate=True).decode("utf-8")
    except ValueError, UnicodeDecodeError:
        return False
    return hmac.compare_digest(decoded, f"{user}:{password}")


def build_public_url(
    url_host: str,
    port: int,
    quality: str,
    config: FrontDoorConfig,
    *,
    max_session_duration: int = 60,
    enableaudio: int = 1,
    fmtp: int = 1,
) -> str:
    """Build the credential-free RTSP URL a recorder should connect to.

    The canonical Bosch path (``/rtsp_tunnel``) + query are embedded so the
    recorder's request is forwarded verbatim to the camera — the same URI that
    the direct-FFmpeg path uses, which keeps SDP/control-URL behaviour proven.
    ``quality`` selects ``inst`` (high=1, low=2). Auth-mode adds an in-URL
    Basic credential or a leading path-token segment (stripped at the gate).
    """
    inst = _QUALITY_INST.get(quality, 1)
    path = (
        f"rtsp_tunnel?inst={inst}&enableaudio={enableaudio}"
        f"&fmtp={fmtp}&maxSessionDuration={max_session_duration}"
    )
    cred = ""
    prefix = ""
    if config.auth_mode == AUTH_BASIC and config.token:
        cred = f"{_urlquote(config.basic_user, safe='')}:{_urlquote(config.token, safe='')}@"
    elif config.auth_mode == AUTH_PATH_TOKEN and config.token:
        prefix = f"{_urlquote(config.token, safe='')}/"
    return f"rtsp://{cred}{url_host}:{port}/{prefix}{path}"


async def _close_writer(writer: asyncio.StreamWriter) -> None:
    """Close ``writer`` and wait for the close to actually complete.

    A bare ``writer.close()`` only schedules the close — under load the
    underlying TCP socket can stay open into TIME_WAIT/linger past the point
    the caller has already moved on and reused the slot (semaphore release,
    idle-linger rearm, etc.), so every close site here now awaits
    ``wait_closed()`` too. ``wait_closed()`` can itself raise on an
    already-broken connection (reset/broken-pipe/OS-level errors) — that's
    expected on an abrupt client/camera disconnect, not a bug, so it's
    swallowed here rather than propagated (matches the file's existing
    best-effort-teardown pattern elsewhere).
    """
    writer.close()
    try:
        await writer.wait_closed()
    except Exception as err:  # best-effort close of an already-abrupt connection
        _LOGGER.debug("frigate front-door: wait_closed() error (non-fatal): %s", err)


# ─────────────────────────────────────────────────────────────────────────────
# Per-connection relay (Digest auth dance + steady injection).
# ─────────────────────────────────────────────────────────────────────────────


class _Relay:
    """Handles one downstream client ↔ inner-proxy connection."""

    def __init__(
        self,
        cam_id: str,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target: InnerTarget,
        first_request: bytes,
    ) -> None:
        self._cam = cam_id[:8]
        self._cr = client_reader
        self._cw = client_writer
        self._target = target
        self._first = first_request
        self._challenge: dict[str, str] | None = None
        self._ir: asyncio.StreamReader | None = None
        self._iw: asyncio.StreamWriter | None = None

    async def run(self) -> None:
        """Connect to the inner proxy, do the auth dance, then pipe both ways."""
        ir, iw = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", self._target.port),
            timeout=_INNER_CONNECT_TIMEOUT,
        )
        self._ir, self._iw = ir, iw
        try:
            if has_authorization_header(self._first):
                # Back-compat: client supplies its own creds → pure passthrough.
                iw.write(self._first)
                await iw.drain()
            else:
                await self._auth_dance()
            await asyncio.gather(
                self._pipe_client_to_inner(),
                self._pipe_inner_to_client(),
            )
        finally:
            for w in (iw, self._cw):
                if not w.is_closing():
                    await _close_writer(w)

    async def _read_message(self, reader: asyncio.StreamReader) -> bytes:
        """Read one full RTSP message head (+body if Content-Length present).

        Bounded by ``_AUTH_READ_TIMEOUT`` so a stalled camera during the auth
        dance can't pin the connection. A response head exceeding asyncio's
        64 KB readuntil limit (``LimitOverrunError``) is treated as a protocol
        error → ConnectionError (caught by ``run``) so both sockets close.
        """
        try:
            head = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"), timeout=_AUTH_READ_TIMEOUT
            )
            body_len = content_length(head)
            if body_len:
                head += await asyncio.wait_for(
                    reader.readexactly(body_len), timeout=_AUTH_READ_TIMEOUT
                )
        except (TimeoutError, asyncio.LimitOverrunError) as err:
            raise ConnectionError(f"inner read failed: {err}") from err
        return head

    async def _auth_dance(self) -> None:
        """Probe for the camera's Digest challenge, then resend authenticated."""
        assert self._ir is not None and self._iw is not None
        self._iw.write(self._first)
        await self._iw.drain()
        resp = await self._read_message(self._ir)
        status = parse_response_status(resp)

        if status != 401:
            # Camera accepted without auth (or unexpected) — forward + steady.
            self._cw.write(resp)
            await self._cw.drain()
            return

        www = extract_header(resp, "WWW-Authenticate")
        if www:
            try:
                self._challenge = _parse_digest_challenge(www)
            except ValueError:
                self._challenge = None
        parsed = parse_request_start_line(self._first)
        if self._challenge and parsed:
            method, uri = parsed
            auth = _build_digest_header(
                method,
                uri,
                self._target.digest_user,
                self._target.digest_password,
                self._challenge,
            )
            self._iw.write(inject_auth_header(self._first, auth))
            await self._iw.drain()
            resp2 = await self._read_message(self._ir)
            # The original 401 is swallowed — never forwarded to the client.
            self._cw.write(resp2)
            await self._cw.drain()
            if parse_response_status(resp2) == 401:
                # Stale creds (Bosch rotated server-side). Forward the honest
                # 401 + close so the recorder reconnects with refreshed creds.
                _LOGGER.debug(
                    "frigate front-door %s: camera rotated Digest creds — closing for reconnect",
                    self._cam,
                )
                self._challenge = None
            return
        # Couldn't compute auth — forward the 401 so the client knows.
        _LOGGER.warning(
            "frigate front-door %s: cannot compute Digest challenge, forwarding 401",
            self._cam,
        )
        self._cw.write(resp)
        await self._cw.drain()

    async def _pipe_client_to_inner(self) -> None:
        """Forward client→inner, injecting a fresh Authorization per request."""
        assert self._ir is not None and self._iw is not None
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
        """Emit every complete request in ``buf``, return the unparsed tail."""
        assert self._iw is not None
        while buf:
            if buf[:1] == b"$":
                # Interleaved RTP/RTCP binary frame — forward raw, never parse.
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
            parsed = parse_request_start_line(req)
            if parsed and self._challenge:
                method, uri = parsed
                try:
                    auth = _build_digest_header(
                        method,
                        uri,
                        self._target.digest_user,
                        self._target.digest_password,
                        self._challenge,
                    )
                    self._iw.write(inject_auth_header(req, auth))
                except ValueError, KeyError:
                    self._iw.write(req)
            else:
                self._iw.write(req)
            await self._iw.drain()
        return b""

    async def _pipe_inner_to_client(self) -> None:
        """Forward inner→client verbatim (RTP frames, responses)."""
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


def _default_relay_factory(
    cam_id: str,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target: Any,
    first_request: bytes,
) -> Relay:
    """The historical, only-ever relay: Digest-injecting `_Relay`.

    `FrontDoorRunner.start_server`'s default `relay_factory` — every
    pre-existing caller (Frigate's own front-door, `viewing_front_door.py`)
    keeps this behaviour unchanged.
    """
    return _Relay(cam_id, client_reader, client_writer, target, first_request)


# ─────────────────────────────────────────────────────────────────────────────
# Front-door server (one per camera) + shared background-loop runner.
# ─────────────────────────────────────────────────────────────────────────────


class _CameraServer:
    """One always-on listener for a single camera."""

    def __init__(
        self,
        cam_id: str,
        config: FrontDoorConfig,
        resolve_inner: ResolveInner,
        on_active: Callable[[], None] | None,
        on_idle: Callable[[], None] | None,
        relay_factory: RelayFactory = _default_relay_factory,
    ) -> None:
        self.cam_id = cam_id
        self.config = config
        self._resolve = resolve_inner
        self._on_active = on_active
        self._on_idle = on_idle
        self._relay_factory = relay_factory
        self._server: asyncio.base_events.Server | None = None
        self._sem = asyncio.Semaphore(self.config.max_connections)
        self.port = 0
        self.client_count = 0
        # Pending zero-client idle-linger task (see _idle_linger). Wired to the
        # frigate_idle_timeout option. (bug-hunt 2026-07-01)
        self._idle_task: asyncio.Task[None] | None = None

    async def start(self, preferred_port: int) -> int:
        """Bind the listener; returns the bound port."""
        self._server = await asyncio.start_server(
            self._handle, self.config.bind_host, preferred_port
        )
        self.port = self._server.sockets[0].getsockname()[1]
        _LOGGER.info(
            "frigate front-door for %s listening on %s:%d (session opens on demand)",
            self.cam_id[:8],
            self.config.bind_host,
            self.port,
        )
        return self.port

    def close(self) -> None:
        """Stop accepting new connections (synchronous, best-effort)."""
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None
        if self._server is not None:
            self._server.close()
            self._server = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_ip = peer[0] if peer else ""
        cam = self.cam_id[:8]
        if not ip_allowed(peer_ip, self.config.ip_allowlist):
            _LOGGER.warning(
                "frigate front-door %s: rejecting client %s (not allowlisted)",
                cam,
                peer_ip,
            )
            await _close_writer(writer)
            return

        if self._sem.locked():
            _LOGGER.warning(
                "frigate front-door %s: connection cap (%d) reached, rejecting %s",
                cam,
                self.config.max_connections,
                peer_ip,
            )
            await _close_writer(writer)
            return
        await self._sem.acquire()

        self.client_count += 1
        if self.client_count == 1:
            # New activity cancels any pending idle-linger teardown.
            if self._idle_task is not None and not self._idle_task.done():
                self._idle_task.cancel()
            self._idle_task = None
            if self._on_active is not None:
                try:
                    self._on_active()
                except Exception as err:  # caller callback must never kill the listener
                    _LOGGER.debug(
                        "frigate front-door %s: on_active raised — %s", cam, err
                    )
        try:
            await self._serve(reader, writer, peer_ip)
        finally:
            self._sem.release()
            self.client_count -= 1
            if self.client_count == 0 and self._on_idle is not None:
                # Linger config.idle_timeout seconds of continuous zero clients
                # before signalling idle, so a recorder that briefly reconnects
                # (segment boundary, go2rtc restream re-open) doesn't thrash the
                # on-demand session. idle_timeout <= 0 → signal immediately
                # ("0 = close immediately", as documented). This wires the
                # previously-dead frigate_idle_timeout option. (bug-hunt 2026-07-01)
                if self._idle_task is not None and not self._idle_task.done():
                    self._idle_task.cancel()
                self._idle_task = asyncio.create_task(self._idle_linger())

    async def _idle_linger(self) -> None:
        """Wait config.idle_timeout of continuous zero-client idle, then fire
        on_idle. Cancelled and replaced the instant a new client connects.
        """
        try:
            if self.config.idle_timeout > 0:
                await asyncio.sleep(self.config.idle_timeout)
        except asyncio.CancelledError:
            return
        self._idle_task = None
        # A client may have arrived (and left) again during the sleep; only
        # signal if we are genuinely still idle.
        if self.client_count == 0 and self._on_idle is not None:
            try:
                self._on_idle()
            except Exception as err:  # caller callback must never kill the listener
                _LOGGER.debug(
                    "frigate front-door %s: on_idle raised — %s",
                    self.cam_id[:8],
                    err,
                )

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_ip: str
    ) -> None:
        cam = self.cam_id[:8]
        try:
            first = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=30)
        except (
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
            TimeoutError,
            OSError,
        ):
            await _close_writer(writer)
            return
        body = content_length(first)
        if body:
            try:
                first += await reader.readexactly(body)
            except asyncio.IncompleteReadError, OSError:
                await _close_writer(writer)
                return

        parsed = parse_request_start_line(first)
        if parsed is None:
            await _close_writer(writer)
            return
        _method, uri = parsed

        # ── Gate auth ────────────────────────────────────────────────────────
        cfg = self.config
        if cfg.auth_mode == AUTH_PATH_TOKEN and cfg.token:
            ok, rewritten = split_path_token(uri, cfg.token)
            if not ok:
                _LOGGER.warning(
                    "frigate front-door %s: bad/missing path token from %s",
                    cam,
                    peer_ip,
                )
                await _close_writer(writer)
                return
            first = _rewrite_request_uri(first, rewritten)
        elif cfg.auth_mode == AUTH_BASIC and cfg.token:
            if not check_basic_auth(first, cfg.basic_user, cfg.token):
                writer.write(
                    b'RTSP/1.0 401 Unauthorized\r\nWWW-Authenticate: Basic realm="bosch-frigate"\r\n\r\n'
                )
                await writer.drain()
                await _close_writer(writer)
                return
            # Strip the gate header so the inner Digest dance starts clean.
            first = _strip_authorization(first)

        # ── Resolve the inner session lazily (opens the Bosch session) ──────
        try:
            target = await asyncio.wait_for(
                self._resolve(self.cam_id), timeout=_RESOLVE_TIMEOUT
            )
        except (
            Exception
        ) as err:  # broad: any resolve failure → drop client, recorder retries
            _LOGGER.debug("frigate front-door %s: resolve_inner failed — %s", cam, err)
            target = None
        if target is None:
            writer.write(b"RTSP/1.0 503 Service Unavailable\r\n\r\n")
            with contextlib.suppress(OSError):
                await writer.drain()
            await _close_writer(writer)
            return

        relay = self._relay_factory(self.cam_id, reader, writer, target, first)
        try:
            await relay.run()
        except (asyncio.IncompleteReadError, ConnectionError, OSError) as err:
            _LOGGER.debug("frigate front-door %s: relay ended — %s", cam, err)


def _rewrite_request_uri(request: bytes, new_uri: str) -> bytes:
    """Replace the request-line URI (2nd token) with ``new_uri``."""
    eol = request.find(b"\r\n")
    if eol < 0:
        return request
    first = request[:eol].decode("utf-8", errors="replace")
    rest = request[eol:]
    parts = first.split(" ")
    if len(parts) < 3:
        return request
    parts[1] = new_uri
    return (" ".join(parts)).encode("utf-8") + rest


def _strip_authorization(request: bytes) -> bytes:
    """Remove any ``Authorization:`` line from the request head."""
    sep = request.find(b"\r\n\r\n")
    if sep < 0:
        return request
    head = request[:sep].decode("utf-8", errors="replace")
    tail = request[sep:]
    kept = [
        ln
        for ln in head.split("\r\n")
        if ln.split(":", 1)[0].strip().lower() != "authorization"
    ]
    return ("\r\n".join(kept)).encode("utf-8") + tail


class FrontDoorRunner:
    """Hosts every camera's front-door server directly on the HA event loop.

    The servers are plain asyncio ``start_server`` listeners and the per-client
    relays are asyncio tasks — all on the loop they are created from (HA's). No
    background thread, so there is no cross-loop bridging to block or leak; the
    lazy ``resolve_inner`` is awaited directly on the same loop.
    """

    def __init__(self) -> None:
        self._servers: dict[str, _CameraServer] = {}

    async def start_server(
        self,
        cam_id: str,
        config: FrontDoorConfig,
        resolve_inner: ResolveInner,
        preferred_port: int = 0,
        on_active: Callable[[], None] | None = None,
        on_idle: Callable[[], None] | None = None,
        relay_factory: RelayFactory = _default_relay_factory,
    ) -> int:
        """Start (or restart) the front-door for ``cam_id``; returns the port.

        ``relay_factory`` defaults to the Digest-injecting `_Relay` used by
        every pre-existing caller (Frigate, `viewing_front_door.py`).
        `remote_viewing_front_door.py` passes its own path-rewriting relay —
        see `Relay`/`RelayFactory` above for why this hook exists.
        """
        self.stop_server(cam_id)
        server = _CameraServer(
            cam_id, config, resolve_inner, on_active, on_idle, relay_factory
        )
        port = await server.start(preferred_port)
        self._servers[cam_id] = server
        return port

    def stop_server(self, cam_id: str) -> None:
        """Close the listener for ``cam_id`` (sync — stops accepting at once)."""
        server = self._servers.pop(cam_id, None)
        if server is not None:
            server.close()

    def active_count(self, cam_id: str) -> int:
        server = self._servers.get(cam_id)
        return server.client_count if server is not None else 0

    def has_server(self, cam_id: str) -> bool:
        return cam_id in self._servers

    def port(self, cam_id: str) -> int:
        server = self._servers.get(cam_id)
        return server.port if server is not None else 0

    def stop_all(self) -> None:
        for cam_id in list(self._servers):
            self.stop_server(cam_id)


class FrigateCoordinatorMixin:
    """Coordinator-facing Frigate/external-recorder front-door management.

    Mixed into BoschCameraCoordinator (see __init__.py's class declaration).
    Every method here is annotated `self: Any` — mirroring the `coordinator:
    Any` convention this codebase already uses for the free-function
    coordinator helpers (fcm.py, live_connection.py) — since this group
    reads/writes many coordinator attributes directly (`_frigate_runner`,
    `_live_connections`, `_tls_proxy_ports`, `data`, `options`, `hass`, …)
    and calls several coordinator methods (`try_live_connection`,
    `_has_active_consumer`, `_tear_down_live_stream`, `_get_session`,
    `get_model_config`). A concrete `self: BoschCameraCoordinator`
    annotation was tried first but mypy --strict rejects it here: proving
    "self is a supertype of FrigateCoordinatorMixin" requires the checker to
    already know BoschCameraCoordinator's bases at THIS module's definition
    site, which is circular (BoschCameraCoordinator's own type depends on
    this mixin). `Any` sidesteps that without losing meaningful type safety
    on the small FCM mixin (which types `hass` directly since it's the only
    attribute that group touches).
    """

    # Bare annotation only (no assignment) — declares the type without
    # creating a class-level default, so mypy doesn't infer a conflicting
    # narrower type (e.g. non-Optional FrontDoorRunner) from the `self:
    # Any`-typed assignment in async_sync_frigate_endpoint below. The real
    # instance attribute is set in BoschCameraCoordinator.__init__.
    frigate_runner: FrontDoorRunner | None

    def _frigate_config(self: Any) -> FrontDoorConfig:
        """Build the front-door config from the integration options."""
        opts = self.options
        raw_allow = str(opts.get("frigate_ip_allowlist", "") or "")
        allowlist = frozenset(p.strip() for p in raw_allow.split(",") if p.strip())
        # NOT `opts.get(..., 60) or 60` — the options-flow schema allows 0
        # (vol.Range(min=0, max=3600)) as an explicit "close immediately"
        # value (frigate_endpoint.py: "if idle_timeout > 0: ... # 0 = close
        # immediately"). `or 60` treats 0 as falsy and silently substitutes
        # the default, making that documented value unreachable — the same
        # class of bug as the previously-dead-until-v14.4.0
        # frigate_idle_timeout option (bug-hunt 2026-07-03).
        idle_timeout_opt = opts.get("frigate_idle_timeout", 60)
        idle_timeout = 60 if idle_timeout_opt is None else idle_timeout_opt
        return FrontDoorConfig(
            bind_host=str(opts.get("frigate_bind_host", "127.0.0.1")),
            ip_allowlist=allowlist,
            auth_mode=str(opts.get("frigate_auth_mode", "none")),
            token=str(opts.get("frigate_token", "") or ""),
            basic_user=str(opts.get("frigate_basic_user", "frigate") or "frigate"),
            idle_timeout=float(idle_timeout),
            max_connections=int(opts.get("frigate_max_connections", 8) or 8),
        )

    def _frigate_url_host(self: Any, bind_host: str) -> str:
        """Host to embed in the published URL.

        - A specific interface IP (e.g. 192.168.1.50) or 127.0.0.1 is routable
          as-is and used verbatim.
        - An all-interfaces bind (0.0.0.0 / :: / empty) isn't routable, so we
          detect the HA host's primary outbound IPv4 (no packet is sent) instead.
        """
        if bind_host not in ("0.0.0.0", "::", ""):  # all-interfaces sentinels
            return bind_host
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            return "127.0.0.1"
        finally:
            sock.close()

    async def _frigate_resolve_inner(self: Any, cam_id: str) -> InnerTarget | None:
        """Lazily ensure a LOCAL live session + inner TLS proxy for a recorder.

        Returns the inner proxy port + the session's rotating Digest creds, or
        None when no LOCAL session is available (e.g. REMOTE-only fallback,
        privacy mode, camera offline) so the front-door drops the client.
        Credential-free injection only works on the LOCAL path.

        Only opens a new session when there is no active LOCAL session — calling
        try_live_connection() unconditionally would issue a PUT /connection on
        Gen2 FW 9.40.25+, rotating Digest credentials and destroying the running
        TLS proxy port every time a recorder reconnects (HA#37 stream-drop loop).
        """
        live = self.live_connections.get(cam_id, {})
        if live.get("_connection_type") != "LOCAL":
            await self.try_live_connection(cam_id)
            live = self.live_connections.get(cam_id, {})
        if live.get("_connection_type") != "LOCAL":
            return None
        port = self.tls_proxy_ports.get(cam_id)
        user = live.get("_local_user")
        pwd = live.get("_local_password")
        if not (port and user and pwd):
            return None
        return InnerTarget(port=port, digest_user=str(user), digest_password=str(pwd))

    def _frigate_wanted(self: Any, cam_id: str) -> bool:
        """True if the feature is enabled AND a High/Low switch is on for cam."""
        if not self.options.get("frigate_endpoints_enabled", False):
            return False
        return bool(
            self.frigate_high_enabled.get(cam_id)
            or self.frigate_low_enabled.get(cam_id)
        )

    def _frigate_on_idle(self: Any, cam_id: str) -> None:
        """Front-door for cam_id has had zero recorder clients for the configured
        frigate_idle_timeout. Tear down the on-demand LOCAL session it opened —
        but ONLY if no OTHER consumer (a live card view, Cast, Mini-NVR) is still
        using it; otherwise do nothing and let the generic idle reaper handle
        teardown when everyone leaves. Runs as a background task because on_idle
        is a synchronous loop callback. (bug-hunt 2026-07-01 — wires the
        previously-dead frigate_idle_timeout option.)
        """

        async def _maybe_teardown() -> None:
            if await self.has_active_consumer(cam_id):
                return  # a live view / recording still needs the session
            live = self.live_connections.get(cam_id)
            if not live or live.get("_connection_type") != "LOCAL":
                return  # nothing LOCAL to tear down
            # Capture the generation at decision time: `_tear_down_live_stream`
            # can now block on the stream lock for the duration of a
            # concurrent rebuild, so by the time it runs, this stale "LOCAL,
            # no consumer" read may no longer describe the current session.
            gen = self.get_session(cam_id).generation
            _LOGGER.info(
                "frigate front-door %s idle for frigate_idle_timeout — tearing "
                "down on-demand LOCAL session",
                cam_id[:8],
            )
            await self.tear_down_live_stream(cam_id, expected_generation=gen)

        task = self.hass.async_create_task(
            _maybe_teardown(), f"bosch_shc_camera_frigate_idle_{cam_id[:8]}"
        )
        self.bg_tasks.add(task)
        task.add_done_callback(self.bg_tasks.discard)

    async def async_sync_frigate_endpoint(self: Any, cam_id: str) -> None:
        """Start or stop the front-door for a camera per current switch state."""
        wanted = self._frigate_wanted(cam_id)
        if not wanted:
            if self.frigate_runner is not None and self.frigate_runner.has_server(
                cam_id
            ):
                self.frigate_runner.stop_server(cam_id)
            return
        if self.frigate_runner is None:
            self.frigate_runner = FrontDoorRunner()
        config = self._frigate_config()
        base_port = int(self.options.get("frigate_bind_port", 0))
        if base_port > 0:
            # Fixed-port mode: compute a stable per-camera port from the sorted
            # list of ALL known cam_ids (sorted → adding a new camera doesn't
            # shift existing cameras' ports). First cam → base, second → base+1, …
            sorted_cams = sorted(self.data.keys()) if self.data else [cam_id]
            idx = sorted_cams.index(cam_id) if cam_id in sorted_cams else 0
            preferred_port = base_port + idx
            try:
                port = await self.frigate_runner.start_server(
                    cam_id,
                    config,
                    self._frigate_resolve_inner,
                    preferred_port=preferred_port,
                    on_idle=lambda: self._frigate_on_idle(cam_id),
                )
                self._frigate_sticky_port[cam_id] = port
            except OSError as err:
                _LOGGER.error(
                    "frigate front-door %s: fixed port %d unavailable (%s) — "
                    "set frigate_bind_port to 0 or pick a free port",
                    cam_id[:8],
                    preferred_port,
                    err,
                )
                return
        else:
            # Ephemeral mode: use in-session sticky port; fall back on collision.
            try:
                port = await self.frigate_runner.start_server(
                    cam_id,
                    config,
                    self._frigate_resolve_inner,
                    preferred_port=self._frigate_sticky_port.get(cam_id, 0),
                    on_idle=lambda: self._frigate_on_idle(cam_id),
                )
                self._frigate_sticky_port[cam_id] = port
            except OSError as err:
                # Sticky port taken (e.g. after a reload) — retry on an ephemeral port.
                _LOGGER.warning(
                    "frigate front-door %s: bind on sticky port failed (%s) — using ephemeral",
                    cam_id[:8],
                    err,
                )
                self._frigate_sticky_port.pop(cam_id, None)
                try:
                    port = await self.frigate_runner.start_server(
                        cam_id,
                        config,
                        self._frigate_resolve_inner,
                        on_idle=lambda: self._frigate_on_idle(cam_id),
                    )
                except OSError as err2:
                    # The first OSError assumed "port taken", but an
                    # ephemeral (port=0) bind still uses frigate_bind_host —
                    # if THAT is the problem (unbindable/nonexistent
                    # interface, bad IPv6 literal, etc.) the retry fails
                    # with the same error, previously uncaught. Since
                    # async_added_to_hass calls this on every HA restart for
                    # a RestoreEntity-restored "on" switch, a bad
                    # frigate_bind_host used to break entity setup with a
                    # traceback on every restart instead of a clear log
                    # (bug-hunt 2026-07-03).
                    _LOGGER.error(
                        "frigate front-door %s: could not bind even an "
                        "ephemeral port (%s) — check frigate_bind_host",
                        cam_id[:8],
                        err2,
                    )
                    return
                self._frigate_sticky_port[cam_id] = port
        # Sensors read the new port/state.
        self.async_update_listeners()

    def frigate_endpoint_url(self: Any, cam_id: str, quality: str) -> str | None:
        """Published credential-free RTSP URL for a camera+quality, or None.

        None when the feature is off, the matching High/Low switch is off, or
        the front-door is not currently bound.
        """
        if not self.options.get("frigate_endpoints_enabled", False):
            return None
        enabled = (
            self.frigate_high_enabled
            if quality == QUALITY_HIGH
            else self.frigate_low_enabled
        )
        if not enabled.get(cam_id):
            return None
        if self.frigate_runner is None or not self.frigate_runner.has_server(cam_id):
            return None
        port = self.frigate_runner.port(cam_id)
        if not port:
            return None
        config = self._frigate_config()
        # Use the camera model's session duration (3600s), not the 60s default —
        # a too-low value can arm a server-side timer that kills the stream.
        msd = int(self.get_model_config(cam_id).max_session_duration)
        return build_public_url(
            self._frigate_url_host(config.bind_host),
            port,
            quality,
            config,
            max_session_duration=msd,
        )

    def async_stop_frigate_endpoints(self: Any) -> None:
        """Tear down all front-doors (integration unload / shutdown)."""
        if self.frigate_runner is not None:
            try:
                self.frigate_runner.stop_all()
            except Exception as err:  # broad: teardown must never block unload
                _LOGGER.debug("frigate front-doors stop_all raised: %s", err)
            self.frigate_runner = None
