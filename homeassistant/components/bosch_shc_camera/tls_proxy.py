"""TLS proxy for Bosch Smart Home Camera LOCAL RTSPS streams.

Bosch cameras use RTSPS (RTSP over TLS) with a self-signed certificate
and Digest auth. FFmpeg/HA's stream component can't handle this combination.
This module provides a TCP→TLS proxy that accepts plain TCP connections on
localhost and forwards them to the camera over TLS. FFmpeg handles Digest
auth itself — the proxy only unwraps TLS.

Runs entirely on the HA asyncio event loop via `asyncio.start_server()` —
no dedicated OS threads, no raw blocking sockets, no module-level listener
state. All server/state ownership lives on the caller-supplied
``port_cache``/``server_cache`` dicts (coordinator-owned in practice), so a
config-entry unload can tear everything down deterministically without a
defensive module-level sweep.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import hashlib
import logging
import re
import socket
import ssl
import time

from .const import TIMEOUT_TLS_PROXY_CONNECT, TIMEOUT_TLS_PROXY_RTSP_READ

_LOGGER = logging.getLogger(__name__)

# Client→camera pipe idle timeout: FFmpeg sends RTSP control traffic
# (SETUP/PLAY/keepalive) on this direction; a dead client silently stops
# sending, so a read timeout is how we detect and clean up. Camera→client
# has no timeout — dark/still scenes can have sparse RTP packets, and TCP
# keepalive already handles a genuinely dead upstream connection.
_CLIENT_TO_CAM_IDLE_TIMEOUT = 120

# Burst-failure circuit breaker: when the camera goes physically offline
# (Privacy hardware button, power cut, WiFi drop) HA's stream worker keeps
# opening new client connections every few seconds, and each one triggers
# an upstream connect attempt that times out. Without a cap we log dozens
# of "failed to connect" warnings and burn time on repeated connect
# timeouts. After _MAX_BURST consecutive failures within _BURST_WINDOW
# seconds we close the server — coordinator will detect the situation and
# either tear down the live session entirely or rebuild it once the
# camera is reachable again (via the on_proxy_died callback).
_MAX_BURST = 5
_BURST_WINDOW = 30.0


async def start_tls_proxy(
    ssl_ctx: ssl.SSLContext,
    cam_id: str,
    cam_host: str,
    cam_port: int,
    port_cache: dict[str, int],
    server_cache: dict[str, asyncio.base_events.Server],
    is_renewal: bool = False,  # kept for call-site/API compat (unused, matches prior behavior)
    on_proxy_died: Callable[[], None] | None = None,
) -> int:
    """Start a local TCP→TLS proxy for a LOCAL RTSPS stream.

    Always creates a fresh proxy on each session — credential changes from
    PUT /connection require a new port so HA's stream worker builds a fresh
    RTSP URL with the new credentials instead of retrying cached old ones.
    """
    # Always stop any existing proxy first — fresh start per session
    if cam_id in port_cache or cam_id in server_cache:
        await stop_tls_proxy(cam_id, port_cache, server_cache)

    # Closure-local circuit-breaker state. Single-threaded event loop means
    # plain `nonlocal` is safe — no cross-thread races, no list-boxing needed
    # (unlike the old thread-based implementation this replaces).
    fail_count = 0
    first_fail_at = float("-inf")
    died_fired = False

    async def _fire_on_proxy_died() -> None:
        nonlocal died_fired
        if died_fired:
            return
        died_fired = True
        # A slow-to-fail connect attempt from THIS generation can still be
        # in flight after a renewal/rebuild has already replaced this
        # proxy for the same cam_id (stop_tls_proxy only guarantees the
        # listening socket + accepted clients are closed, not that every
        # in-flight upstream-connect coroutine has unwound). Only touch the
        # shared caches — and only fire the rebuild callback — if they
        # still point at THIS server; otherwise this is a stale trip and
        # must not evict/orphan the newer, healthy generation or trigger a
        # spurious rebuild of an already-fine session.
        is_current = server_cache.get(cam_id) is server
        if is_current:
            server_cache.pop(cam_id, None)
            port_cache.pop(cam_id, None)
        try:
            server.close()
        except OSError as close_exc:  # best-effort close, callback below still fires
            _LOGGER.debug(
                "TLS proxy %s: server.close() during circuit-breaker raised — %s",
                cam_id[:8],
                close_exc,
            )
        if not is_current:
            _LOGGER.debug(
                "TLS proxy %s: circuit breaker fired for a stale/superseded "
                "generation — closed its own server but skipped caches and "
                "on_proxy_died (a newer proxy is already active)",
                cam_id[:8],
            )
            return
        if on_proxy_died is not None:
            try:
                on_proxy_died()
            except Exception as cb_exc:  # noqa: BLE001 -- caller-supplied callback, arbitrary exception surface
                _LOGGER.debug(
                    "TLS proxy %s: on_proxy_died callback raised — %s",
                    cam_id[:8],
                    cb_exc,
                )

    async def _pipe(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        rewrite_transport: bool,
        direction: str,
        idle_timeout: float | None,
    ) -> None:
        """Forward bytes. If rewrite_transport=True, intercept RTSP SETUP
        requests and force TCP interleaved transport so FFmpeg doesn't try
        UDP (which can't work through the TCP proxy).
        """
        interleaved_counter = 0
        dbg_count = 0
        try:
            while True:
                try:
                    if idle_timeout is not None:
                        data = await asyncio.wait_for(
                            reader.read(65536), timeout=idle_timeout
                        )
                    else:
                        data = await reader.read(65536)
                except TimeoutError:
                    break
                if not data:
                    break
                if dbg_count < 20 and len(data) < 2000 and data[:1] != b"$":
                    dbg_count += 1
                    preview = (
                        data[:500]
                        .decode("utf-8", errors="replace")
                        .replace("\r\n", "\\r\\n")
                    )
                    # Redact auth headers — Authorization carries the
                    # computed Digest response; WWW-Authenticate carries
                    # realm/nonce from the camera challenge.
                    preview = re.sub(
                        r"(?i)(Authorization:|WWW-Authenticate:)[^\\]*",
                        r"\1 <redacted>",
                        preview,
                    )
                    _LOGGER.debug(
                        "TLS proxy %s [%s] %d bytes: %.500s",
                        cam_id[:8],
                        direction,
                        len(data),
                        preview,
                    )
                if rewrite_transport and b"SETUP " in data:
                    # Replace UDP transport with TCP interleaved
                    text = data.decode("utf-8", errors="replace")
                    lo = interleaved_counter
                    hi = lo + 1
                    text = re.sub(
                        r"Transport:\s*RTP/AVP[^;\r\n]*;unicast;client_port=[^\r\n]+",
                        f"Transport: RTP/AVP/TCP;unicast;interleaved={lo}-{hi}",
                        text,
                    )
                    interleaved_counter = hi + 1
                    data = text.encode("utf-8")
                writer.write(data)
                await writer.drain()
        except OSError as exc:
            # Peer closed / reset / SSL error — expected during session
            # teardown (e.g. after credential rotation), not a real error.
            _LOGGER.debug(
                "TLS proxy %s [%s] pipe error: %s", cam_id[:8], direction, exc
            )
        finally:
            writer.close()

    async def _handle_client(
        client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        nonlocal fail_count, first_fail_at
        try:
            tls_reader, tls_writer = await asyncio.wait_for(
                asyncio.open_connection(
                    cam_host,
                    cam_port,
                    ssl=ssl_ctx,
                    server_hostname=cam_host,
                ),
                timeout=TIMEOUT_TLS_PROXY_CONNECT,
            )
        except OSError as exc:
            now = time.monotonic()
            if fail_count == 0:
                first_fail_at = now
            fail_count += 1
            # Per-attempt failure is benign during a brief camera WLAN
            # dropout — it auto-recovers and only the burst/circuit-breaker
            # below (≥_MAX_BURST in _BURST_WINDOW) signals a real outage.
            _LOGGER.debug(
                "TLS proxy %s: failed to connect to %s:%d — %s",
                cam_id[:8],
                cam_host,
                cam_port,
                exc,
            )
            client_writer.close()
            if fail_count >= _MAX_BURST and (now - first_fail_at) <= _BURST_WINDOW:
                _LOGGER.warning(
                    "TLS proxy %s: %d consecutive connect failures in %.0fs — "
                    "closing server socket (camera unreachable). "
                    "Coordinator will rebuild the session when the camera is back.",
                    cam_id[:8],
                    fail_count,
                    now - first_fail_at,
                )
                # Awaited inline: server.close() is non-blocking and
                # on_proxy_died() itself only schedules a coordinator task
                # (never awaits), so this can't stall or deadlock this
                # handler's own cleanup.
                await _fire_on_proxy_died()
            return

        # Reset failure burst — a successful connect proves the camera is
        # reachable again.
        fail_count = 0
        first_fail_at = float("-inf")
        ssl_obj = tls_writer.get_extra_info("ssl_object")
        _LOGGER.debug(
            "TLS proxy %s: connected to %s:%d (TLS %s, cipher %s)",
            cam_id[:8],
            cam_host,
            cam_port,
            ssl_obj.version() if ssl_obj is not None else "?",
            ((ssl_obj.cipher() or ("?",))[0] if ssl_obj is not None else "?"),
        )
        _set_keepalive(client_writer)
        _set_keepalive(tls_writer)

        try:
            await asyncio.gather(
                _pipe(
                    client_reader,
                    tls_writer,
                    rewrite_transport=True,
                    direction="C→CAM",
                    idle_timeout=_CLIENT_TO_CAM_IDLE_TIMEOUT,
                ),
                _pipe(
                    tls_reader,
                    client_writer,
                    rewrite_transport=False,
                    direction="CAM→C",
                    idle_timeout=None,
                ),
                return_exceptions=True,
            )
        finally:
            client_writer.close()
            tls_writer.close()

    server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
    port: int = server.sockets[0].getsockname()[1]
    port_cache[cam_id] = port
    server_cache[cam_id] = server
    _LOGGER.info(
        "TLS proxy for %s started on 127.0.0.1:%d -> %s:%d (asyncio)",
        cam_id[:8],
        port,
        cam_host,
        cam_port,
    )
    return port


def _set_keepalive(writer: asyncio.StreamWriter) -> None:
    """Best-effort TCP keep-alive tuning on a StreamWriter's socket."""
    sock = writer.get_extra_info("socket")
    if sock is None:
        return
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except AttributeError, OSError:
        pass


async def stop_tls_proxy(
    cam_id: str,
    port_cache: dict[str, int],
    server_cache: dict[str, asyncio.base_events.Server],
) -> None:
    """Stop the TLS proxy for a camera by closing its server.

    `Server.close()` alone only stops accepting NEW connections — it
    leaves any already-accepted client (FFmpeg/go2rtc) connections open.
    `Server.wait_closed()` blocks until BOTH the server is closed AND every
    active connection has dropped, so without also actively closing those
    connections (`close_clients()`, Python 3.13+), this would hang forever
    whenever a stream is actively connected at stop time — turning a
    routine teardown (switch off, reconfigure, config-entry unload) into a
    deadlock.
    """
    port_cache.pop(cam_id, None)
    server = server_cache.pop(cam_id, None)
    if server is not None:
        try:
            server.close()
            server.close_clients()
            await server.wait_closed()
            _LOGGER.debug("TLS proxy for %s: server closed", cam_id[:8])
        except OSError:
            pass


async def stop_all_proxies(
    port_cache: dict[str, int],
    server_cache: dict[str, asyncio.base_events.Server],
) -> None:
    """Stop all TLS proxies — called during integration unload."""
    for cam_id in list(server_cache.keys()):
        await stop_tls_proxy(cam_id, port_cache, server_cache)
    # Belt-and-suspenders: if stop_tls_proxy left any entries (shouldn't
    # happen, but guards against future refactors).
    port_cache.clear()
    server_cache.clear()


async def rtsp_keepalive(
    proxy_port: int, user: str, password: str, cam_id: str
) -> bool:
    """Send an RTSP OPTIONS keepalive through the proxy to prevent 60s timeout.

    The Bosch camera enforces a 60-second session timeout regardless of
    maxSessionDuration in the URL.  Sending an authenticated OPTIONS every
    ~30s resets the inactivity timer and keeps the TCP connection alive for
    FFmpeg/go2rtc.

    Returns True if the keepalive succeeded (camera replied 200 OK).
    """
    writer = None  # track so the exception path can close it if opened
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", proxy_port), timeout=5
        )
        uri = f"rtsp://127.0.0.1:{proxy_port}/rtsp_tunnel"

        # Step 1: OPTIONS without auth → 401 + realm/nonce
        writer.write(f"OPTIONS {uri} RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode())
        await writer.drain()
        resp1 = await asyncio.wait_for(
            reader.read(4096), timeout=TIMEOUT_TLS_PROXY_RTSP_READ
        )
        resp1_str = resp1.decode("utf-8", errors="replace")

        nonce_m = re.search(r'nonce="([^"]+)"', resp1_str)
        realm_m = re.search(r'realm="([^"]+)"', resp1_str)
        if not (nonce_m and realm_m):
            # Camera may respond 200 without auth challenge — that's fine too
            if "200 OK" in resp1_str:
                _LOGGER.debug(
                    "Keepalive OPTIONS 200 OK (no auth needed) on port %d", proxy_port
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except (
                    OSError
                ):  # best-effort writer close after keepalive, failure non-actionable
                    pass
                return True
            _LOGGER.debug(
                "Keepalive: no nonce/realm on port %d (%.100s)", proxy_port, resp1_str
            )
            writer.close()
            try:
                await writer.wait_closed()
            except (
                OSError
            ):  # best-effort writer close after keepalive, failure non-actionable
                pass
            return False

        nonce, realm = nonce_m.group(1), realm_m.group(1)
        auth = _digest_auth(user, password, "OPTIONS", uri, realm, nonce)

        # Step 2: authenticated OPTIONS
        writer.write(
            f"OPTIONS {uri} RTSP/1.0\r\n"
            f"CSeq: 2\r\n"
            f"Authorization: {auth}\r\n"
            f"\r\n".encode()
        )
        await writer.drain()
        resp2 = await asyncio.wait_for(
            reader.read(4096), timeout=TIMEOUT_TLS_PROXY_RTSP_READ
        )
        resp2_str = resp2.decode("utf-8", errors="replace")
        writer.close()
        try:
            await writer.wait_closed()
        except (
            OSError
        ):  # best-effort writer close after keepalive, failure non-actionable
            pass

        if "200 OK" in resp2_str:
            _LOGGER.debug("Keepalive OPTIONS 200 OK on port %d", proxy_port)
            return True
        _LOGGER.debug(
            "Keepalive: unexpected response on port %d: %.100s", proxy_port, resp2_str
        )
        return False
    except OSError as exc:
        _LOGGER.debug("Keepalive failed on port %d: %s", proxy_port, exc)
        # Close a writer opened before the failure — a read-timeout or drain
        # error after open_connection succeeded would otherwise leak one
        # fd/socket per keepalive (runs ~every 30s). Mirrors pre_warm_rtsp.
        if writer is not None:
            try:
                writer.close()
                await writer.wait_closed()
            except (
                OSError
            ):  # best-effort writer close on keepalive failure, failure non-actionable
                pass
        return False


def _digest_auth(
    user: str,
    password: str,
    method: str,
    uri: str,
    realm: str,
    nonce: str,
) -> str:
    """Compute Digest auth header value."""
    ha1 = hashlib.md5(
        f"{user}:{realm}:{password}".encode(), usedforsecurity=False
    ).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode(), usedforsecurity=False).hexdigest()
    resp = hashlib.md5(
        f"{ha1}:{nonce}:{ha2}".encode(), usedforsecurity=False
    ).hexdigest()
    return (
        f'Digest username="{user}",realm="{realm}",'
        f'nonce="{nonce}",uri="{uri}",response="{resp}"'
    )


async def pre_warm_rtsp(
    proxy_port: int,
    user: str,
    password: str,
    cam_host: str,
    max_attempts: int = 5,
    retry_wait: int = 3,
    post_success_wait: int = 3,
    describe_timeout: int = 5,
    max_session_duration: int = 60,
) -> bool:
    """Pre-warm camera's H.264 encoder via authenticated RTSP DESCRIBE.

    After PUT /connection LOCAL returns credentials, the camera needs a moment
    to initialize its encoder. Sending an authenticated DESCRIBE (codec
    negotiation) wakes the encoder so it's ready when FFmpeg connects.

    Only DESCRIBE — no SETUP/PLAY — so no RTSP session is created.
    This avoids conflicts with FFmpeg which needs to start its own session.

    Sequence: DESCRIBE (unauth) → 401 → DESCRIBE (digest) → 200 OK (SDP)

    Retries with configurable attempts and delay. Timing is model-specific:
    CAMERA_360 (indoor) is faster, CAMERA_EYES (outdoor) needs more retries.

    Returns True on success (got 200 OK to DESCRIBE), False on hard failure
    (all attempts exhausted or camera unreachable). The caller uses this to
    decide whether to fall back to REMOTE: if the camera's LAN IP isn't
    reachable from HA (firewall, wrong subnet, different VLAN), every retry
    times out and we should not pin the user on a dead LOCAL URL.

    ``max_session_duration`` is substituted into the DESCRIBE URI so the
    pre-warm and the subsequent FFmpeg stream share the same session-duration
    value.  If Bosch uses the DESCRIBE URI to configure the server-side timer,
    a mismatched value here (old hard-coded 60 s) could start a 60-second
    countdown before FFmpeg connects — silently starving long-session models
    (e.g. Indoor Gen2 with maxSessionDuration=3600).
    """
    for attempt in range(1, max_attempts + 1):
        writer = (
            None  # track so exception path can close it if open_connection succeeded
        )
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
            uri = (
                f"rtsp://127.0.0.1:{proxy_port}"
                f"/rtsp_tunnel?inst=1&enableaudio=1&fmtp=1&maxSessionDuration={max_session_duration}"
            )

            # Step 1: DESCRIBE without auth → 401 + nonce/realm
            writer.write(
                f"DESCRIBE {uri} RTSP/1.0\r\n"
                f"CSeq: 1\r\n"
                f"Accept: application/sdp\r\n"
                f"\r\n".encode()
            )
            await writer.drain()
            resp1 = await asyncio.wait_for(reader.read(4096), timeout=describe_timeout)

            # Step 2: Parse nonce, send authenticated DESCRIBE
            resp1_str = resp1.decode("utf-8", errors="replace")
            nonce_m = re.search(r'nonce="([^"]+)"', resp1_str)
            realm_m = re.search(r'realm="([^"]+)"', resp1_str)
            if not (nonce_m and realm_m):
                _LOGGER.debug(
                    "Pre-warm RTSP: no nonce/realm in response (port %d, attempt %d/%d): %.200s",
                    proxy_port,
                    attempt,
                    max_attempts,
                    resp1_str,
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except (
                    OSError
                ):  # best-effort writer close on pre-warm abort, failure non-actionable
                    pass
                if attempt < max_attempts:
                    await asyncio.sleep(retry_wait)
                    continue
                return False
            nonce, realm = nonce_m.group(1), realm_m.group(1)

            auth = _digest_auth(user, password, "DESCRIBE", uri, realm, nonce)
            writer.write(
                f"DESCRIBE {uri} RTSP/1.0\r\n"
                f"CSeq: 2\r\n"
                f"Accept: application/sdp\r\n"
                f"Authorization: {auth}\r\n"
                f"\r\n".encode()
            )
            await writer.drain()
            resp2 = await asyncio.wait_for(reader.read(8192), timeout=describe_timeout)
            resp2_str = resp2.decode("utf-8", errors="replace")

            got_ok = "200 OK" in resp2_str
            if got_ok:
                _LOGGER.debug(
                    "Pre-warm RTSP complete (DESCRIBE 200 OK) on port %d", proxy_port
                )
            else:
                # Non-200 DESCRIBE during creds rotation is recoverable — the
                # caller falls back gracefully (FFmpeg retries the connect).
                # → DEBUG, not WARNING.
                _LOGGER.debug(
                    "Pre-warm RTSP: unexpected response on port %d: %.200s",
                    proxy_port,
                    resp2_str,
                )

            writer.close()
            try:
                await writer.wait_closed()
            except OSError:  # best-effort writer close after pre-warm DESCRIBE, failure non-actionable
                pass
            # Wait for the camera to fully release the TLS connection.
            # The camera only allows ~2 concurrent RTSP sessions per
            # PUT /connection credential set. Without this delay, FFmpeg
            # may connect before the pre-warm's TLS session is torn down.
            await asyncio.sleep(post_success_wait)
            return got_ok
        except OSError as exc:
            _LOGGER.debug(
                "Pre-warm RTSP failed on port %d (attempt %d/%d): %s",
                proxy_port,
                attempt,
                max_attempts,
                exc,
            )
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except OSError:  # best-effort writer close in pre-warm exception handler, failure non-actionable
                    pass
            if attempt < max_attempts:
                await asyncio.sleep(retry_wait)
    return False
