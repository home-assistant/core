"""Always-on, credential-free RTSP front-door for the MAIN live-viewing path.

Problem (HA-Core-submission prep, 2026-07-14): HA-core's own built-in go2rtc
integration automatically registers a stream with go2rtc on every WebRTC
offer, using whatever `camera.stream_source()` currently returns — no opt-in
required, this happens for free once the integration is Core-eligible.
go2rtc's registration is purely additive: it dedupes only on an exact
URL-string match and offers no API to remove a stale entry. This integration's
LOCAL `stream_source()` URL embeds real, frequently-rotating Bosch Digest
credentials (`rtsp://user:pass@127.0.0.1:PORT/...`) — creds that rotate on
every heartbeat PUT /connection, as fast as ~15s on Gen1 cameras — and a fresh
ephemeral TLS-proxy port on every session rebuild. Relying on native
registration with that URL shape would leak a new dead go2rtc entry roughly
every 15 seconds per actively-streaming Gen1 camera, forever (HA process
lifetime — go2rtc's registry has no eviction for entries that fall out of
use).

This module reuses the exact same proven pattern already shipped for the
opt-in external-recorder front-door (`frigate_endpoint.py`, HA#37): a
stable-port, credential-free RTSP listener that performs the Digest
challenge/response dance itself (harvesting the challenge fresh, injecting
`Authorization` using the live session's current rotating creds) instead of
requiring the client to supply credentials. It reuses the SAME inner
`tls_proxy.py` port and the SAME live Bosch session the main viewing path
already opened — this module never opens a second session itself, matching
`frigate_endpoint.py`'s `_frigate_resolve_inner` "reuse, don't open" contract
(see that function's docstring for why an unconditional `try_live_connection()`
call here would be actively harmful: it would issue a PUT /connection on
Gen2 FW 9.40.25+, rotating Digest credentials and destroying the running TLS
proxy port on every resolve). Unlike the Frigate resolver, this one has no
lazy-open fallback at all — by the time it runs, the main viewing flow
(`live_connection.py`) has always already opened the LOCAL session that
populates `_live_connections`/`_tls_proxy_ports`, so there is nothing useful
for a fallback branch to do.

Because the listener's bound port never changes and the URL it publishes
never embeds credentials, `stream_source()` can return the SAME URL string
across every credential rotation — the front-door reads the freshest
`_local_user`/`_local_password` out of `coordinator.live_connections[cam_id]`
fresh on every client (re)connect, so native go2rtc registration stays a
single, stable, dedup-friendly entry for the lifetime of a camera's LOCAL
session.

This is the "main viewing path" always-reused counterpart to
`frigate_endpoint.py`'s opt-in external-recorder front-door — separate state
(`coordinator.viewing_front_door_runner` / `_viewing_sticky_port`), separate
`FrontDoorRunner` instance, but built entirely out of that module's generic,
feature-agnostic building blocks (`FrontDoorRunner`, `FrontDoorConfig`,
`InnerTarget`). Always bound to `127.0.0.1` with no IP allowlist and no gate
auth (`AUTH_NONE`) — this front-door exists purely to keep the *published
URL* stable and credential-free for HA-internal consumers (HA's own Stream/
FFmpeg, go2rtc), not to expose the stream to other hosts on the LAN (that is
what the separate, explicitly opt-in Frigate front-door is for).
"""

from __future__ import annotations

import logging
from typing import Any

from .frigate_endpoint import AUTH_NONE, FrontDoorConfig, FrontDoorRunner, InnerTarget

_LOGGER = logging.getLogger(__name__)


async def viewing_resolve_inner(coordinator: Any, cam_id: str) -> InnerTarget | None:
    """Return the current inner TLS-proxy port + live Digest creds, or None.

    Deliberately does NOT call `try_live_connection()` — unlike
    `frigate_endpoint._frigate_resolve_inner`'s lazy-open fallback, the main
    viewing path (`live_connection.py`) always already has an active LOCAL
    session open by the time this front-door is started (it is only ever
    started AFTER a successful pre-warm, from within
    `try_live_connection_inner` itself). Adding a lazy-open fallback here
    would risk the exact credential-rotation-kills-the-proxy bug
    `_frigate_resolve_inner`'s docstring warns about, for no benefit — there
    is no code path where this front-door's listener is running but the
    viewing session it belongs to has not yet been opened.

    Returns None (front-door replies 503, client/recorder retries) when
    there is no active LOCAL session for this camera — e.g. the session was
    torn down, fell back to REMOTE, or the inner TLS proxy hasn't finished
    starting yet.
    """
    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "LOCAL":
        return None
    port = coordinator.tls_proxy_ports.get(cam_id)
    user = live.get("_local_user")
    pwd = live.get("_local_password")
    if not (port and user and pwd):
        return None
    return InnerTarget(port=port, digest_user=str(user), digest_password=str(pwd))


async def start_viewing_front_door(
    coordinator: Any,
    cam_id: str,
    *,
    inst: int,
    audio_param: str,
    max_session_duration: int,
) -> str | None:
    """Start (or reuse) the credential-free viewing front-door for `cam_id`.

    Returns the credential-free, stable-port RTSP URL to publish via
    `stream_source()`, or None if the listener could not be bound at all
    (caller should fall back to the raw credentialed URL so streaming still
    works, just without the credential-free/stable-port benefit).

    The URL shape is constructed directly here (not via
    `frigate_endpoint.build_public_url`) rather than reusing that function's
    `quality`-based abstraction: `build_public_url` is owned by, and evolves
    with, the separate opt-in Frigate/external-recorder feature (it also
    adds Frigate-specific concerns like path-token/Basic-auth gating that
    don't apply here, since this front-door is always AUTH_NONE). Coupling
    this always-on, HA-internal-consumers-only feature's URL shape to that
    function's future changes would be the wrong dependency direction — the
    query-string SHAPE below is instead kept byte-for-byte identical to the
    existing `local_rtsp_url` construction in `live_connection.py` (minus
    the `user:pass@` credential prefix), since that is the contract HA's
    Stream component / go2rtc / FFmpeg already rely on.
    """
    if coordinator.viewing_front_door_runner is None:
        coordinator.viewing_front_door_runner = FrontDoorRunner()
    runner = coordinator.viewing_front_door_runner
    if runner.has_server(cam_id):
        # Already bound — genuinely REUSE it rather than restart
        # (bug-hunt finding: `FrontDoorRunner.start_server` always does an
        # internal stop_server()+rebind, which is fine for a fresh connect
        # but is unnecessary churn on every periodic LOCAL session renewal —
        # `viewing_resolve_inner` reads `_tls_proxy_ports`/`_local_user`/
        # `_local_password` fresh on every client (re)connect, so a
        # renewal's new inner TLS-proxy port is picked up automatically by
        # the EXISTING listener with no rebind needed. Restarting here would
        # needlessly ECONNREFUSE any client racing the close→rebind gap —
        # the same "don't restart what doesn't need restarting" class of
        # bug already fixed elsewhere in this codebase for the NVR recorder
        # on heartbeat cred rotation, HA#41/#42). The URL is still rebuilt
        # from THIS call's `inst`/`audio_param`/`max_session_duration` (a
        # quality change on a fresh, non-renewal call still gets reflected
        # in the returned URL even though the listener itself is untouched).
        return (
            f"rtsp://127.0.0.1:{runner.port(cam_id)}/rtsp_tunnel"
            f"?inst={inst}{audio_param}&fmtp=1&maxSessionDuration={max_session_duration}"
        )
    config = FrontDoorConfig(bind_host="127.0.0.1", auth_mode=AUTH_NONE)
    try:
        port = await runner.start_server(
            cam_id,
            config,
            lambda cid: viewing_resolve_inner(coordinator, cid),
            preferred_port=coordinator.viewing_sticky_port.get(cam_id, 0),
        )
    except OSError as err:
        # Sticky port taken (e.g. after a reload) — retry on an ephemeral
        # port. Mirrors frigate_endpoint.py's async_sync_frigate_endpoint
        # ephemeral-mode two-tier OSError handling exactly.
        _LOGGER.warning(
            "viewing front-door %s: bind on sticky port failed (%s) — using ephemeral",
            cam_id[:8],
            err,
        )
        coordinator.viewing_sticky_port.pop(cam_id, None)
        try:
            port = await runner.start_server(
                cam_id,
                config,
                lambda cid: viewing_resolve_inner(coordinator, cid),
            )
        except OSError as err2:
            # The first OSError assumed "port taken", but an ephemeral
            # (port=0) bind still uses `config.bind_host` — if THAT is the
            # problem (unbindable/nonexistent interface) the retry fails
            # with the same error, so it must be caught separately rather
            # than left to propagate out of this function.
            _LOGGER.error(
                "viewing front-door %s: could not bind even an ephemeral port (%s)",
                cam_id[:8],
                err2,
            )
            return None
    coordinator.viewing_sticky_port[cam_id] = port
    return (
        f"rtsp://127.0.0.1:{port}/rtsp_tunnel?inst={inst}{audio_param}"
        f"&fmtp=1&maxSessionDuration={max_session_duration}"
    )


async def stop_viewing_front_door(coordinator: Any, cam_id: str) -> None:
    """Stop the viewing front-door listener for `cam_id`, if one is running."""
    if coordinator.viewing_front_door_runner is not None:
        coordinator.viewing_front_door_runner.stop_server(cam_id)
