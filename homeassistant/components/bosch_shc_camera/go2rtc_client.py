"""go2rtc stream unregistration + go2rtc WebRTC-provider scheme refresh.

Originally Phase 3 step 3 of the coordinator-rewrite split (see
docs/stream-perf-stability-refactor-plan.md): the bodies below were the
former `BoschCameraCoordinator` methods `_ensure_go2rtc_schemes_fresh`,
`_register_go2rtc_stream` and `_unregister_go2rtc_stream`, moved out
unchanged except for `self` → `coordinator`.

`register_go2rtc_stream` (the manual `PUT /api/streams` call) was removed
2026-07-14 (HA-Core-submission-prep): HA-core's own bundled go2rtc
integration already auto-registers whatever `camera.stream_source()`
returns on every WebRTC offer (`homeassistant/components/go2rtc/__init__.py`
`WebRTCProvider._update_stream_source`), so a manual PUT duplicated
Core-owned protocol logic reviewers push back on. This only became safe
once both LOCAL (`viewing_front_door.py`) and REMOTE
(`remote_viewing_front_door.py`) started publishing a STABLE URL per
session — go2rtc's registration is purely additive with no removal API, so
registering a URL that changed on every credential rotation (as fast as
~15s on Gen1 LOCAL sessions) would have leaked a fresh dead entry every
time; native auto-registration only became viable once that churn was
fixed at the source. `unregister_go2rtc_stream` (`DELETE /api/streams`) is
KEPT — there is no native equivalent at all (go2rtc's registration API has
no removal call, confirmed by reading `python-go2rtc-client`'s actual
surface), so this remains the only way to keep the registry tidy on a
genuine session teardown (as opposed to the URL churn problem the removed
PUT call no longer needs to guard against).

`ensure_go2rtc_schemes_fresh` is unrelated to registration — a separate
workaround for an HA-core provider-initialization race — and unaffected.

`BoschCameraCoordinator` keeps a thin same-named method for each remaining
function that delegates here — exercised extensively from other
coordinator-facing modules (stream_lifecycle.py) and from the test suite
both as bound methods and via `BoschCameraCoordinator._method(coord, ...)`
unbound-style calls plus direct `AsyncMock()` attribute patching — all of
which requires the method to keep existing on the class.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import time
from typing import TYPE_CHECKING, cast

import aiohttp

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def _get_go2rtc_session(
    coordinator: BoschCameraCoordinator,
) -> aiohttp.ClientSession:
    """Lazily create/return the coordinator's shared go2rtc-API session.

    go2rtc is reached over plain HTTP on localhost (11984/1984) — a
    different trust domain from the Bosch-cloud TLS session in cloud_ssl.py,
    so it gets its own pooled session instead of reusing that one. Was
    previously a fresh `aiohttp.ClientSession()` per call on all three
    go2rtc call sites (go2rtc_consumer_count / register_go2rtc_stream /
    unregister_go2rtc_stream — Work Package 1,
    stream-perf-stability-refactor). Closed exactly once, in
    _async_cancel_coordinator_tasks (__init__.py), on config-entry unload /
    HA stop.

    A free function taking `coordinator` explicitly (matching the existing
    poll_statuses/poll_events/run_housekeeping/try_live_connection_inner
    pattern in this codebase) rather than a coordinator method — it uses
    getattr/setattr instead of direct attribute access so the many
    SimpleNamespace-based coordinator test doubles in tests/test_init.py
    keep working without every one of them growing a
    `_go2rtc_session`/`_go2rtc_session_lock` attribute.
    """
    existing: aiohttp.ClientSession | None = getattr(
        coordinator, "go2rtc_session", None
    )
    if existing is not None and not existing.closed:
        return existing
    if getattr(coordinator, "go2rtc_teardown_done", False):
        # _async_cancel_coordinator_tasks already ran and closed the shared
        # session for good (unload/HA-stop). A stray caller racing that
        # teardown — e.g. camera.py's stream_source() from a live frontend
        # request landing in the gap between _async_cancel_coordinator_tasks
        # and hass.config_entries.async_unload_platforms in
        # async_unload_entry — must NOT lazily mint a brand-new session here:
        # nothing will ever close it again (teardown only runs once per
        # unload/stop), so it would leak ("Unclosed client session"). Raise
        # RuntimeError instead — every one of the three go2rtc call sites
        # already catches RuntimeError and treats it like an unreachable
        # endpoint (see the (..., RuntimeError) except clauses below).
        raise RuntimeError("go2rtc session unavailable — coordinator is shutting down")
    lock = getattr(coordinator, "go2rtc_session_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        coordinator.go2rtc_session_lock = lock
    async with lock:
        # Double-check inside the lock — another coroutine may have already
        # created it while we awaited the lock (register/unregister/
        # consumer-count can all fire concurrently across cameras).
        existing = cast(
            "aiohttp.ClientSession | None",
            getattr(coordinator, "go2rtc_session", None),
        )
        if existing is not None and not existing.closed:
            return existing
        if getattr(coordinator, "go2rtc_teardown_done", False):
            raise RuntimeError(
                "go2rtc session unavailable — coordinator is shutting down"
            )
        session = aiohttp.ClientSession()
        coordinator.go2rtc_session = session
        return session


@asynccontextmanager
async def _go2rtc_client_session(
    coordinator: BoschCameraCoordinator,
) -> AsyncIterator[aiohttp.ClientSession]:
    """Yield the shared, pooled session for one localhost go2rtc API call.

    Used to take an optional `connector` param for the removed
    `register_go2rtc_stream`'s Unix-socket-first-try path (HA-Core-
    submission-prep, 2026-07-14 — see the module docstring) — the only
    caller that ever needed a private, non-pooled session. The two
    remaining callers (`unregister_go2rtc_stream`,
    `stream_lifecycle.go2rtc_consumer_count`) always want the shared,
    plain-TCP-to-127.0.0.1 session, so the connector branch was dead code
    once removal landed; simplified accordingly rather than left unreachable.
    """
    yield await _get_go2rtc_session(coordinator)


async def ensure_go2rtc_schemes_fresh(coordinator: BoschCameraCoordinator) -> None:
    """Pre-emptively re-fetch `_supported_schemes` directly on the existing WebRTCProvider instance(s).

    This makes the very first stream activation find the right scheme set,
    avoiding the race where the card asks for capabilities before the
    post-stream watchdog had a chance to fire.

    Direct-refresh (private-API hack) instead of full config-entry reload,
    because reload was found to not actually populate the schemes set in
    time before camera state writes happen — the bundled go2rtc binary
    may not yet be answering `/api/schemes` when the new provider's
    `initialize()` runs during reload, so the fresh provider also caches
    an empty set. Calling `provider._rest_client.schemes.list()` directly
    on the existing instance bypasses the reload churn and pulls the
    current scheme list now that go2rtc is ready.
    """
    if not hasattr(coordinator, "last_schemes_refresh"):
        coordinator.last_schemes_refresh = float("-inf")
    now = time.monotonic()
    if now - coordinator.last_schemes_refresh < 600:
        return
    try:
        from homeassistant.components.camera.webrtc import DATA_WEBRTC_PROVIDERS
    except ImportError:
        return
    providers = coordinator.hass.data.get(DATA_WEBRTC_PROVIDERS, set())
    if not providers:
        return
    coordinator.last_schemes_refresh = now
    refreshed = False
    for provider in providers:
        if not hasattr(provider, "_rest_client") or not hasattr(
            provider, "_supported_schemes"
        ):
            continue  # not the bundled go2rtc provider
        try:
            fresh = await provider._rest_client.schemes.list()
            if fresh:
                old_count = len(provider._supported_schemes)
                provider._supported_schemes = fresh
                refreshed = True
                _LOGGER.info(
                    "webrtc-watchdog: refreshed go2rtc provider _supported_schemes "
                    "(was %d schemes, now %d)",
                    old_count,
                    len(fresh),
                )
        except Exception as err:  # noqa: BLE001 -- one provider's failure (private go2rtc-provider internals) must not abort refreshing the rest
            _LOGGER.debug("webrtc-watchdog: scheme-refresh failed: %s", err)
    # Push the now-fresh provider to every camera entity that has STREAM
    # in supported_features. Without this, cams that ran async_refresh_providers
    # against a stale scheme set keep `_webrtc_provider = None` cached, and
    # the next `camera/capabilities` query advertises only HLS — even though
    # the provider's schemes are now fresh. The auto-fire only triggers on
    # `supported_features & STREAM` flips, but our streams may already be up.
    if refreshed:
        from homeassistant.components.camera import CameraEntityFeature

        for cam_id_x, cam_ent in list(coordinator.camera_entities.items()):
            # Only touch cameras that already have an active session.
            # HA Core's `async_refresh_providers` calls `stream_source()`
            # on the entity, which our implementation answers with
            # `try_live_connection()` — opening a fresh LOCAL stream on
            # idle cams the user never asked to view. Bug 2026-05-20:
            # Innenbereich woke up streaming after this loop ran on a
            # Terrasse stream-open. Guard added so the watchdog stays
            # scoped to the cam that triggered it.
            if cam_id_x not in coordinator.live_connections:
                continue
            try:
                if CameraEntityFeature.STREAM in cam_ent.supported_features:
                    await cam_ent.async_refresh_providers()
                    _LOGGER.debug(
                        "webrtc-watchdog: refreshed providers on %s",
                        getattr(cam_ent, "entity_id", "?"),
                    )
            except Exception as err:  # noqa: BLE001 -- one camera's async_refresh_providers() failure must not abort the watchdog pass for the rest
                _LOGGER.debug(
                    "webrtc-watchdog: cam refresh-providers failed for %s: %s",
                    getattr(cam_ent, "entity_id", "?"),
                    err,
                )


async def unregister_go2rtc_stream(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> None:
    """Remove the camera stream from go2rtc when the live session ends.

    Name must match register_go2rtc_stream — prefer camera.entity_id
    (HA's bundled go2rtc provider uses this) and fall back to the legacy
    internal name when the entity is unavailable.
    """
    cam_entity = coordinator.camera_entities.get(cam_id)
    if cam_entity is not None and cam_entity.entity_id:
        stream_name = cam_entity.entity_id
    else:
        stream_name = f"bosch_shc_cam_{cam_id.lower()}"
    # Try both ports the stream could have been registered on (11984 on HA
    # 2024+, 1984 legacy) — DELETE must reach whichever one HA-core's own
    # go2rtc provider actually used to auto-register it.
    endpoints = [
        "http://localhost:11984/api/streams",
        "http://localhost:1984/api/streams",
    ]
    for url in endpoints:
        try:
            async with asyncio.timeout(3):
                async with _go2rtc_client_session(coordinator) as s:
                    resp = await s.delete(url, params={"name": stream_name})
                    # Only a real removal (200/204) ends the loop. aiohttp
                    # does not raise on 4xx/5xx, so an unconditional break
                    # would stop on a 404 (stream registered on the OTHER
                    # port) or a 500 and never reach the endpoint where the
                    # stream actually lives — defeating the documented
                    # multi-endpoint retry and leaking a stale stream (with
                    # its dead proxy port) in go2rtc.
                    if resp.status in (200, 204):
                        _LOGGER.debug(
                            "go2rtc stream '%s' removed via %s (HTTP %d)",
                            stream_name,
                            url,
                            resp.status,
                        )
                        break
                    _LOGGER.debug(
                        "go2rtc DELETE '%s' via %s → HTTP %d — trying next endpoint",
                        stream_name,
                        url,
                        resp.status,
                    )
        except TimeoutError, aiohttp.ClientError, RuntimeError:
            # RuntimeError: the shared go2rtc session can be mid-close/
            # closed if this call raced coordinator teardown.
            pass  # go2rtc may not be running on this port — try next
