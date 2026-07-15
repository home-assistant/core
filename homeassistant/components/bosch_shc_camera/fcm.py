"""FCM push notifications and alert routing for Bosch Smart Home Camera.

Extracted from __init__.py to keep the coordinator lean.
All functions that previously used `self` now take a `coordinator` parameter.

Handles:
  - Firebase Cloud Messaging registration + listening
  - Bosch CBS device token registration
  - 3-step alert pipeline (text -> snapshot -> video clip)
  - Per-type notification routing (information/screenshot/video/system)
  - Event mark-as-read on Bosch cloud
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import time
from typing import Any, ClassVar, TYPE_CHECKING, override
from urllib.parse import urlparse

import aiohttp

from .cloud_ssl import async_get_bosch_cloud_session
from .recorder import assemble_and_ship_motion_clip, should_record
from .snapshot_store import save_snapshot

# ── URL allowlist for image/video downloads (SSRF prevention) ────────────────
_SAFE_DOMAINS = frozenset({".boschsecurity.com", ".bosch.com"})

# Event types that carry image data and warrant a live-snapshot refresh (Path A).
# Status-only types (connectivity events) are excluded — they carry no image
# data and the camera view hasn't changed. Hoisted to module level so it isn't
# rebuilt on every event-fetch pass.
_SNAP_EVENT_TYPES = frozenset(
    {"MOVEMENT", "PERSON", "VEHICLE", "ANIMAL", "AUDIO_ALARM", "BABY_CRY"}
)


def _is_safe_bosch_url(url: str) -> bool:
    """Validate that a URL points to a known Bosch domain (HTTPS only)."""
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and any(parsed.hostname.endswith(d) for d in _SAFE_DOMAINS)
    )


def _safe_path_segment(seg: str) -> str:
    """Neutralise path-traversal in a filename segment.

    The alert snapshot filename embeds the cloud-provided camera title, which
    must never be able to escape the alert directory (e.g. a camera named
    "../../config/secrets"). Strips path separators and parent-dir tokens.
    """
    return str(seg).replace("/", "_").replace("\\", "_").replace("..", "_")


if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CLOUD_API = "https://residential.cbs.boschsecurity.com"

# Supervisor backoff ladder (seconds). The supervisor task waits this long
# between failed listener start/restart attempts. Step 0 (5 s) covers a
# transient connection drop after a push was received; later steps handle
# persistent Google registration problems. Resets to 0 after a successful
# push arrives so a quick recovery doesn't block the next outage detection.
FCM_SUPERVISOR_BACKOFF_SEC: tuple[float, ...] = (
    5.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1800.0,
)

# How often the supervisor polls is_started() while the listener is running.
# 10 s means a listener death is detected within 10 s, not 60 s (the old
# coordinator-tick cadence). Short enough to be reactive; long enough to avoid
# spinning the event loop.
FCM_SUPERVISOR_POLL_SEC = 10.0

# After this many consecutive soft-restarts WITHOUT a real push arriving, the
# next restart escalates to a hard-heal (credential purge + re-register).
FCM_SUPERVISOR_SOFT_HEAL_MAX = 3

# Proactive Bosch-CBS re-registration cadence (issue #36). The integration used
# to skip the POST /v11/devices forever as long as the FCM token was unchanged.
# If Bosch drops the device registration server-side (FW upgrade, re-pair, or an
# undocumented TTL) while our token stays the same, push delivery silently dies
# and nothing ever re-announces us. A real phone app re-registers on every
# launch; we re-POST at least this often (wall-clock, persisted in
# `fcm_registered_at`) even when the token is unchanged, matching that behaviour.
FCM_REREGISTER_INTERVAL_SEC = 7 * 24 * 3600  # 7 days


class _FCMNoiseFilter(logging.Filter):
    """Tame the firebase_messaging FCM client log noise during WAN outages.

    When the WAN drops (router reboot, ISP blip), `firebase_messaging`'s
    `_listen` loop crashes on `await reader.readexactly(1)` and re-enters
    itself recursively while retrying — every ERROR log line carries a
    ~3000-frame stack trace. With a 30 s reconnect cadence that produces
    ~200 log lines/s, 12 k+ lines/min, and an HA CPU spike from ~30 % to
    ~85 % until WAN comes back. Library has no way to suppress the trace
    (issue sdb9696/firebase-messaging#33 covers the abort-on-error angle
    but not the recursive trace).

    Filter strategy:
      1. Strip `exc_info` from the record so the formatter doesn't dump
         the recursive stack — the plain message is enough to know the
         FCM connection failed.
      2. De-duplicate: at most one pass-through per 300 s (5 min) window.
         The library's reconnect cadence is ~63 s on a permanently-broken
         SSL session (upstream `_reset()` retry loop). A 60 s window would
         let every retry through; 300 s gives a heartbeat without flooding
         and matches what the watchdog needs to flip to polling-fallback.
    """

    _DEDUP_WINDOW_SECONDS = 300.0
    _SHARED_STALENESS_TIMESTAMPS: ClassVar[
        list[float]
    ] = []  # only creds-rejection markers

    # Credential-rejection markers: Google's gcm_register() endpoint returned
    # PHONE_REGISTRATION_ERROR (only path that emits this — see
    # firebase_messaging/fcmregister.py). Reaches us only when the library
    # falls through to gcm_register() because gcm_check_in(android_id,
    # security_token) failed or no credentials were persisted. Presence in the
    # log window is the authoritative signal that credentials are actually
    # stale — that's when a hard-heal (purge + fresh register) is warranted.
    _CREDS_STALENESS_MARKERS = (
        "PHONE_REGISTRATION_ERROR",  # GCM auth rejected
        "Unable to complete gcm auth request",  # final-give-up after PHONE_REGISTRATION_ERROR retries
        "Unable to establish subscription",  # fcm.py's wrapper for the above
    )

    # Connectivity-loop marker: WAN blip / SSL reset. Tracked only for log
    # deduplication — NOT used for health decisions (the supervisor detects
    # listener death via is_started()=False, so error counting is unnecessary).
    _CONNECTIVITY_MARKERS = (
        "Unexpected exception during read",  # library reconnect loop
    )

    _FAILURE_MARKERS = _CONNECTIVITY_MARKERS + _CREDS_STALENESS_MARKERS

    def __init__(self) -> None:
        super().__init__()
        self._last_passed = float("-inf")  # monotonic ts of last record we let through

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        # Only target known failure markers; other firebase_messaging logs
        # (INFO start/stop, debug traces) pass through untouched so we keep
        # diagnostic visibility.
        msg = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)
        if not any(marker in msg for marker in self._FAILURE_MARKERS):
            return True
        # Drop the multi-thousand-line traceback unconditionally — the
        # message itself is the diagnostic, the trace is library-internal
        # recursion that doesn't help triage.
        record.exc_info = None
        record.exc_text = None
        now = time.monotonic()
        # Track creds-rejection markers so the supervisor can decide
        # soft (preserve creds) vs hard (purge + re-register) —
        # PHONE_REGISTRATION_ERROR in the window means creds are genuinely
        # stale, otherwise it's a connectivity-only blip.
        if any(marker in msg for marker in self._CREDS_STALENESS_MARKERS):
            self._SHARED_STALENESS_TIMESTAMPS.append(now)
            del self._SHARED_STALENESS_TIMESTAMPS[:-10]
        # Then de-dupe.
        if (now - self._last_passed) < self._DEDUP_WINDOW_SECONDS:
            return False
        self._last_passed = now
        return True


def get_recent_fcm_creds_staleness_count(window_seconds: float = 600.0) -> int:
    """How many `PHONE_REGISTRATION_ERROR`-class markers fired in the
    last ``window_seconds``.

    The two-stage self-heal uses this to decide soft vs hard:
      - count == 0 → creds likely valid, try soft-heal first (no purge)
      - count >= 1 → creds genuinely rejected by Google, hard-heal (purge + register)

    Default window 600 s (10 min) is wide enough to catch the prior
    failure-storm but narrow enough that an old incident doesn't poison a
    fresh outage hours later.
    """
    if not _FCMNoiseFilter._SHARED_STALENESS_TIMESTAMPS:
        return 0
    cutoff = time.monotonic() - window_seconds
    return sum(1 for ts in _FCMNoiseFilter._SHARED_STALENESS_TIMESTAMPS if ts >= cutoff)


def reset_fcm_creds_staleness_counter() -> None:
    """Clear the creds-staleness timestamp list after a hard-heal registration."""
    _FCMNoiseFilter._SHARED_STALENESS_TIMESTAMPS.clear()


def reset_fcm_error_counter() -> None:
    """Backward-compat shim used by tests; delegates to reset_fcm_creds_staleness_counter."""
    reset_fcm_creds_staleness_counter()


async def async_start_fcm_push(coordinator: Any) -> None:
    """Backward-compat shim; production code uses async_ensure_fcm_supervisor.

    Lazy-inits _fcm_start_lock, then delegates to _async_start_fcm_push_locked.
    Used by legacy tests that target the inner lock-and-start logic directly.
    """
    lock = getattr(coordinator, "_fcm_start_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        coordinator._fcm_start_lock = lock
    async with lock:
        await _async_start_fcm_push_locked(coordinator)


def _install_fcm_noise_filter() -> None:
    """Install the noise filter on both relevant loggers once.

    Two loggers can emit "Unexpected exception during read":
      1. ``firebase_messaging.fcmpushclient`` — the vanilla library path (when
         ``_QuietFcmPushClient`` is not used or the patch falls back).
      2. ``custom_components.bosch_shc_camera.fcm`` (``_LOGGER``) — the
         ``_QuietFcmPushClient._listen()`` override also logs via ``_LOGGER``
         in its fallback ``else`` branch (for non-ConnectionReset OSErrors or
         if the run_state guard does not fire).

    A single shared ``_FCMNoiseFilter`` instance is installed on BOTH loggers so
    ``_last_passed`` and ``_SHARED_ERROR_TIMESTAMPS`` are identical regardless of
    which logger emits the record — the 300 s dedup window spans both sources.

    Idempotent: re-running finds the existing instance and returns early.
    """
    # Find or create the shared filter instance.
    lib_logger = logging.getLogger("firebase_messaging.fcmpushclient")
    for f in lib_logger.filters:
        if isinstance(f, _FCMNoiseFilter):
            # Already installed on the library logger.  Make sure the bosch
            # logger also carries it (handles reload after a partial install).
            if f not in _LOGGER.filters:
                _LOGGER.addFilter(f)
            return

    shared_filter = _FCMNoiseFilter()
    lib_logger.addFilter(shared_filter)
    _LOGGER.addFilter(shared_filter)


class _QuietFcmPushClient:
    """FcmPushClient subclass that fixes the upstream state-machine bug described in
    github.com/sdb9696/firebase-messaging#33.

    Root cause (b — state-machine bug):
      In the library's ``_listen()`` while-loop, when an ``OSError``/``EOFError``
      is caught the existing quiet-path check is:

          if (isinstance(osex, (ConnectionResetError, TimeoutError, ...))
              and self.run_state == FcmPushClientRunState.RESETTING):
              <log quietly>
          else:
              _logger.exception("Unexpected exception during read\\n")  # ← noise

      ``run_state`` is only set to ``RESETTING`` *inside* ``_reset()``, which is
      called **after** the logging decision.  So the very first connectivity error
      always takes the loud ``_logger.exception`` path, even though the connection
      is about to be gracefully reset.  On a permanent WAN outage the library
      re-enters this path every ~63 s producing one error (or many thousands of
      lines without ``_FCMNoiseFilter``).

    Fix: override ``_listen()`` and set ``self.run_state = RESETTING`` immediately
    on catching the OS error, **before** the existing quiet-path check fires.  This
    makes the check evaluate to True on the first error, routing to the verbose
    (INFO-level) path instead of ``_logger.exception``.  The rest of the method body
    — including the call to ``_reset()`` — is byte-identical to the library version
    so no happy-path behaviour changes.

    Import-time guard: the class body is only evaluated when ``firebase_messaging``
    is importable (inside ``async_start_fcm_push``).  If the import fails we fall
    back to the vanilla ``FcmPushClient`` transparently.
    """

    # _make() is called inside async_start_fcm_push after a successful import so
    # the try/except there already handles ImportError.
    @staticmethod
    def _patch_class() -> type | None:
        """Return a patched FcmPushClient subclass, or None if the library is too
        new/old for safe subclassing (i.e. ``_listen`` signature changed)."""
        try:
            from firebase_messaging import FcmPushClient, FcmPushClientRunState
        except ImportError:
            return None

        import inspect

        # Safety guard: if the upstream _listen() signature ever changes (e.g.
        # gains a parameter) we must not silently break it.  Fall back to vanilla
        # if the signature is unexpected.
        sig = inspect.signature(FcmPushClient._listen)
        if list(sig.parameters) != ["self"]:
            _LOGGER.debug(
                "FCM subclass: upstream _listen() signature changed — "
                "falling back to vanilla FcmPushClient (issue#33 noise may recur)"
            )
            return None

        class _Patched(FcmPushClient):  # type: ignore[misc]
            """FcmPushClient with the run_state-before-log fix for issue #33."""

            async def _listen(self) -> None:
                """Override _listen to set RESETTING state before the error-log decision.

                Identical to upstream except for the single line that sets
                ``self.run_state = FcmPushClientRunState.RESETTING`` at the top of
                the ``except (OSError, EOFError)`` handler.  This makes the
                existing quiet-path check pass on the very first connectivity error,
                routing to INFO-level logging instead of ``_logger.exception``.
                """
                if not await self._connect_with_retry():
                    return

                try:
                    await self._login()

                    while self.do_listen:
                        try:
                            if self.run_state == FcmPushClientRunState.RESETTING:  # type: ignore[has-type]  # external FcmPushClient attr (untyped base)
                                await asyncio.sleep(1)
                            elif msg := await self._receive_msg():
                                await self._handle_message(msg)

                        except (OSError, EOFError) as osex:
                            # FIX for issue #33: advance state to RESETTING here,
                            # before the quiet-path check below — the library only
                            # sets it inside _reset() which is called afterwards.
                            # Without this line, the first OS error always takes the
                            # _logger.exception() branch even though the connection
                            # is about to be gracefully reset.
                            if self.run_state not in (  # type: ignore[has-type]  # external FcmPushClient attr (untyped base)
                                FcmPushClientRunState.RESETTING,
                                FcmPushClientRunState.STOPPING,
                                FcmPushClientRunState.STOPPED,
                            ):
                                self.run_state = FcmPushClientRunState.RESETTING

                            if (
                                isinstance(
                                    osex,
                                    (
                                        ConnectionResetError,
                                        TimeoutError,
                                        asyncio.IncompleteReadError,
                                        ssl.SSLError,
                                    ),
                                )
                                and self.run_state == FcmPushClientRunState.RESETTING
                            ):
                                if (
                                    isinstance(osex, ssl.SSLError)
                                    and osex.reason
                                    != "APPLICATION_DATA_AFTER_CLOSE_NOTIFY"
                                ):
                                    self._log_warn_with_limit(
                                        "Unexpected SSLError reason during reset of %s",
                                        osex.reason,
                                    )
                                else:
                                    self._log_verbose(
                                        "Expected read error during reset: %s",
                                        type(osex).__name__,
                                    )
                            else:
                                _LOGGER.exception("Unexpected exception during read\n")
                                # Import ErrorType lazily — it is a private enum in
                                # the library module, not exported via __all__.
                                # If the import fails (future refactor) we skip the
                                # error counter; the self-heal watchdog still fires.
                                try:
                                    from firebase_messaging.fcmpushclient import (
                                        ErrorType as _ErrorType,
                                    )

                                    if self._try_increment_error_count(
                                        _ErrorType.CONNECTION
                                    ):
                                        await self._reset()
                                except ImportError:
                                    await self._reset()
                except Exception as ex:
                    import traceback as _tb

                    _LOGGER.error(
                        "Unknown error: %s, shutting down FcmPushClient.\n%s",
                        ex,
                        _tb.format_exc(),
                    )
                    self._terminate()
                finally:
                    await self._do_writer_close()

        return _Patched

    # Module-level cache so _patch_class() runs at most once per process.
    _patched_class: type | None | bool = False  # False = not yet computed


def _get_fcm_push_client_class() -> type | None:
    """Return the patched FcmPushClient subclass (or vanilla if patch failed).

    Cached after the first call.
    """
    if _QuietFcmPushClient._patched_class is False:
        _QuietFcmPushClient._patched_class = _QuietFcmPushClient._patch_class()
    result = _QuietFcmPushClient._patched_class
    if result is None:
        # Patch failed — fall back to vanilla
        try:
            from firebase_messaging import FcmPushClient

            return FcmPushClient  # type: ignore[no-any-return]  # value is correct at runtime; HA/external source is Any-typed
        except ImportError:
            return None
    return result  # type: ignore[return-value]  # False-sentinel already replaced before this point


# Firebase Cloud Messaging — push notifications from Bosch CBS
FCM_SENDER_ID = "404630424405"  # public app-level identifier — same in every Android APK; intentional in source


# ── Firebase config ──────────────────────────────────────────────────────────


async def fetch_firebase_config(hass: HomeAssistant) -> dict[str, str]:
    """Return Firebase config for the Bosch Smart Camera app.

    These are public app-level identifiers embedded in every copy of the
    Bosch Smart Camera APK — they identify the app to Firebase, not the user.
    The API key is restricted by Firebase project rules (not by secrecy).
    """
    project_id = "bosch-smart-cameras"
    app_id = f"1:{FCM_SENDER_ID}:android:9e5b6b58e4c70075"
    import base64

    # Vendor-sanctioned OSS Firebase API key (2026-04-20) — FCM permissions confirmed for OSS use.
    _k = base64.b64decode(
        "QUl6YVN5Q0toaGZ4ZlRzMUc3V3Z6VERBaU8wQWlzN0VIMjVEYk9z"
    ).decode()
    return {
        "project_id": project_id,
        "app_id": app_id,
        "api_key": _k,
    }


# ── FCM start / stop ────────────────────────────────────────────────────────


async def async_ensure_fcm_supervisor(coordinator: Any) -> None:
    """Start the FCM supervisor task if FCM is enabled and not already running.

    This is the single entry point for FCM lifecycle management. The supervisor
    task keeps the push listener alive with automatic restart and exponential
    backoff — call sites no longer need to manage heals or cool-downs.
    Idempotent: safe to call while the supervisor is already running.
    """
    if not coordinator.options.get("enable_fcm_push", False):
        return
    sup = getattr(coordinator, "_fcm_supervisor_task", None)
    if sup is not None and not sup.done():
        return
    coordinator._fcm_supervisor_task = asyncio.ensure_future(
        _async_run_fcm_supervisor(coordinator),
    )
    coordinator._fcm_supervisor_task.set_name("bosch_shc_camera_fcm_supervisor")


async def async_stop_fcm_supervisor(coordinator: Any) -> None:
    """Cancel the FCM supervisor task, then stop the push listener."""
    sup = getattr(coordinator, "_fcm_supervisor_task", None)
    if sup is not None and not sup.done():
        sup.cancel()
        try:
            await sup
        except (asyncio.CancelledError, Exception):  # noqa: S110 — intentional silent cancel
            pass
        coordinator._fcm_supervisor_task = None
    await async_stop_fcm_push(coordinator)


async def _async_start_fcm_push_locked(coordinator: Any) -> bool:
    """Start the FCM push listener. Caller must hold `coordinator._fcm_start_lock`.

    Returns True if the listener started successfully, False otherwise.
    """
    if coordinator._fcm_running:
        return True
    if not coordinator.options.get("enable_fcm_push", False):
        _LOGGER.debug("FCM push disabled in options")
        return False

    try:
        from firebase_messaging import FcmRegisterConfig
    except ImportError:
        _LOGGER.warning("firebase-messaging not installed — FCM push disabled")
        return False

    # Use our patched subclass that fixes the upstream state-machine bug (issue #33):
    # it sets run_state=RESETTING before the error-log decision so transient WAN
    # errors are routed to INFO-level rather than _logger.exception().
    FcmPushClient = _get_fcm_push_client_class()
    if FcmPushClient is None:
        _LOGGER.warning("firebase-messaging not installed — FCM push disabled")
        return False

    # FcmPushClientConfig landed in firebase-messaging 0.4; guard defensively
    # so older installs still start (without the hardening).
    try:
        from firebase_messaging import FcmPushClientConfig
    except ImportError:  # pragma: no cover — 0.4+ ships this symbol
        FcmPushClientConfig = None

    # Determine push mode — only "auto" (use OSS FCM key) or "polling" (skip FCM).
    # Legacy values "ios"/"android" from older versions coerce to "auto".
    push_mode = coordinator.options.get("fcm_push_mode", "auto")
    if push_mode not in ("auto", "polling"):
        push_mode = "auto"

    async def _build_fcm_cfg() -> dict[str, str]:
        """Return the OSS-sanctioned Firebase config (single source, no per-mode split)."""
        cfg = coordinator._entry.data.get("fcm_config") or {}
        if not cfg:
            cfg = await fetch_firebase_config(coordinator.hass)
            if cfg:
                coordinator.hass.config_entries.async_update_entry(
                    coordinator._entry,
                    data={**coordinator._entry.data, "fcm_config": cfg},
                )
        return cfg

    async def _try_fcm() -> bool:
        """Attempt FCM registration with the OSS key. Returns True on success."""
        fcm_cfg = await _build_fcm_cfg()
        if not fcm_cfg.get("api_key"):
            _LOGGER.warning("FCM: could not obtain Firebase config")
            return False

        fcm_config = FcmRegisterConfig(
            project_id=fcm_cfg["project_id"],
            app_id=fcm_cfg["app_id"],
            api_key=fcm_cfg["api_key"],
            messaging_sender_id=FCM_SENDER_ID,
        )

        # Load saved FCM credentials from config entry (survives HA restarts)
        saved_fcm_creds = coordinator._entry.data.get("fcm_credentials")

        # Bound AFTER coordinator._fcm_client is assigned below. Read via
        # late-binding closure (not captured by value) so the comparison in
        # _persist() below always reflects which client THIS _try_fcm() call
        # created — not whatever coordinator._fcm_client points to by the
        # time the callback actually fires.
        _this_client: Any = None

        def _on_creds_updated(creds: Any) -> None:
            """Save FCM credentials to config entry for persistence.

            WHY threadsafe: this callback fires from the FCM client's own
            thread (Firebase SDK), not from the HA event loop. Calling
            `async_update_entry` directly from a foreign thread corrupts
            HA's internal state. `call_soon_threadsafe` hops back onto
            the loop before scheduling the async task.
            """

            def _persist() -> None:
                # Guard against a stale client: a hard-heal purges creds and
                # starts a fresh client+checkin while an OLD client's
                # callback (fired from its own SDK thread, not necessarily
                # covered by the drain-wait in async_stop_fcm_push) can still
                # land on the loop afterwards. Without this check the late
                # callback would silently overwrite the fresh credentials
                # with stale ones, defeating the hard-heal it was meant to
                # recover from (bug-hunt 2026-07-03).
                if coordinator._fcm_client is not _this_client:
                    _LOGGER.debug(
                        "FCM: ignoring credentials_updated_callback from a "
                        "stale/replaced client"
                    )
                    return
                coordinator.hass.async_create_task(
                    _async_persist_fcm_creds(coordinator, creds)
                )

            coordinator.hass.loop.call_soon_threadsafe(_persist)

        def _on_push(
            notification: dict[str, Any], persistent_id: str, obj: Any = None
        ) -> None:
            """Called when a push notification arrives from Bosch CBS."""
            _on_fcm_push(coordinator, notification, persistent_id, obj)

        # v10.3.22: harden against firebase-messaging#33. Default config aborts
        # the listener after 3 sequential CONNECTION errors (e.g. WAN blip) and
        # never reconnects — the client goes silent, our sensor keeps reporting
        # "fcm_push" while no pushes arrive. Passing None disables the abort;
        # library handles normal reconnect. Coordinator-tick watchdog below
        # (__init__.py) flips _fcm_healthy=False if no push in 1h, so the
        # dashboard sensor still shows the degraded state.
        fcm_kwargs = {
            "callback": _on_push,
            "fcm_config": fcm_config,
            "credentials": saved_fcm_creds,
            "credentials_updated_callback": _on_creds_updated,
        }
        if FcmPushClientConfig is not None:
            fcm_kwargs["config"] = FcmPushClientConfig(
                abort_on_sequential_error_count=None,
            )
        coordinator._fcm_client = FcmPushClient(**fcm_kwargs)
        _this_client = coordinator._fcm_client

        try:
            coordinator._fcm_token = await coordinator._fcm_client.checkin_or_register()
            _LOGGER.debug("FCM registered — token: %s...", coordinator._fcm_token[:8])
        except Exception as err:
            # Log diagnostic details that survive _FCMNoiseFilter. The raw
            # error message often contains substrings the filter dedups
            # ("PHONE_REGISTRATION_ERROR", "Unable to establish subscription"),
            # which can starve the operator of visibility into WHY the heal
            # ladder keeps tripping. Mask the marker substrings so the
            # filter doesn't dedup this diagnostic line.
            err_type = type(err).__name__
            err_short = str(err)[:240].replace("\n", " ")
            # Mask FCMNoiseFilter markers so this line passes through.
            for marker in (
                "PHONE_REGISTRATION_ERROR",
                "Unable to complete gcm auth request",
                "Unable to establish subscription",
                "Unexpected exception during read",
            ):
                err_short = err_short.replace(
                    marker, marker.replace("_", "·").replace(" ", "·")
                )
            _LOGGER.warning(
                "FCM checkin/register raised %s — %s",
                err_type,
                err_short,
            )
            coordinator._fcm_client = None
            return False

        # Register FCM token with Bosch CBS API. coordinator._fcm_push_mode is
        # still "unknown" at this point (set to "auto" only after client.start()).
        await register_fcm_with_bosch(coordinator)

        # Start listening for pushes
        try:
            await coordinator._fcm_client.start()
            with coordinator._fcm_lock:
                coordinator._fcm_running = True
                coordinator._fcm_healthy = True
                coordinator._fcm_started_at = time.monotonic()
                coordinator._fcm_push_mode = "auto"
            _LOGGER.info(
                "FCM push listener started — near-instant event detection active"
            )
            return True
        except Exception as err:
            _LOGGER.warning("FCM push listener failed to start: %s", err)
            with coordinator._fcm_lock:
                coordinator._fcm_client = None
            return False

    # Install once before any FCM client is created so the very first WAN
    # outage doesn't spam 12 k+ recursive-traceback lines at us.
    _install_fcm_noise_filter()

    if push_mode == "polling":
        _LOGGER.info("FCM push mode set to 'polling' — using standard API polling only")
        return False

    # "auto" — try FCM with the OSS-sanctioned key; on failure the supervisor
    # will retry automatically (see _async_run_fcm_supervisor backoff ladder).
    result = await _try_fcm()
    if not result:
        _LOGGER.info(
            "FCM registration failed — falling back to standard polling "
            "(supervisor will retry with exponential backoff)"
        )
    return result


async def register_fcm_with_bosch(coordinator: Any) -> bool:
    """Register our FCM token with Bosch CBS so it sends us push notifications.

    Endpoint: POST /v11/devices {"deviceType": "ANDROID", "deviceToken": token}
    Response: HTTP 204 on success. deviceType is always ANDROID — the OSS
    Firebase app registered with Bosch lives under the Android app_id.
    """
    if not coordinator._fcm_token or not coordinator.token:
        return False

    # Skip re-registration only when BOTH conditions hold:
    #   1. The same FCM device token was already registered in a previous run.
    #   2. The registration used deviceType=ANDROID (marker written since Fix C++).
    # If either is false the POST fires to heal any drift.
    #
    # Drift scenario (live bug 2026-05-18): migration v2→v3 without Fix C left
    # fcm_registered_token intact but wrote no fcm_registered_device_type marker.
    # Old skip-logic fired on token==token, leaving Bosch CBS with deviceType=IOS
    # while the HA client used the Android Firebase context. All FCM pushes were
    # routed to the wrong sub-app for hours (latency 3:43 min → polling fallback).
    # Fix: require the ANDROID marker before allowing the skip.
    stored_token: str | None = coordinator._entry.data.get("fcm_registered_token")
    stored_device_type: str | None = coordinator._entry.data.get(
        "fcm_registered_device_type"
    )
    # Proactive re-registration (issue #36): even when the token is unchanged,
    # re-POST if the last successful registration is older than
    # FCM_REREGISTER_INTERVAL_SEC so a server-side-dropped Bosch device
    # registration self-heals without needing a token change or a hard-heal.
    registered_at_raw = coordinator._entry.data.get("fcm_registered_at")
    try:
        registered_at = float(registered_at_raw) if registered_at_raw else 0.0
    except (TypeError, ValueError):
        registered_at = 0.0
    registration_stale = (time.time() - registered_at) > FCM_REREGISTER_INTERVAL_SEC
    if (
        stored_token == coordinator._fcm_token
        and stored_device_type == "ANDROID"
        and not registration_stale
    ):
        _LOGGER.debug(
            "FCM: token unchanged + deviceType=ANDROID verified + registration "
            "fresh — skipping re-registration"
        )
        return True
    if (
        stored_token == coordinator._fcm_token
        and stored_device_type == "ANDROID"
        and registration_stale
    ):
        _LOGGER.info(
            "FCM: Bosch CBS registration older than %d days — re-POSTing to keep "
            "push delivery alive (token unchanged)",
            FCM_REREGISTER_INTERVAL_SEC // 86400,
        )
    if stored_token == coordinator._fcm_token and stored_device_type != "ANDROID":
        _LOGGER.info(
            "FCM CBS heal: token unchanged but deviceType marker is %r (not ANDROID) — "
            "forcing re-registration as deviceType=ANDROID",
            stored_device_type,
        )

    session = await async_get_bosch_cloud_session(coordinator.hass)
    headers = {
        "Authorization": f"Bearer {coordinator.token}",
        "Content-Type": "application/json",
    }
    payload = {"deviceType": "ANDROID", "deviceToken": coordinator._fcm_token}

    try:
        async with asyncio.timeout(10):
            async with session.post(
                f"{CLOUD_API}/v11/devices", headers=headers, json=payload
            ) as resp:
                if resp.status in (200, 201, 204):
                    coordinator.hass.config_entries.async_update_entry(
                        coordinator._entry,
                        data={
                            **coordinator._entry.data,
                            "fcm_registered_token": coordinator._fcm_token,
                            "fcm_registered_device_type": "ANDROID",
                            "fcm_registered_at": time.time(),
                        },
                    )
                    _LOGGER.info(
                        "FCM token registered with Bosch CBS as deviceType=ANDROID (HTTP %d)",
                        resp.status,
                    )
                    return True
                resp_body = await resp.text()
                if resp.status == 500 and "sh:internal.error" in resp_body:
                    # Bosch returns 500 "sh:internal.error" when the same device
                    # token is already registered — FCM push still works. Treat as
                    # success and save both markers so subsequent restarts skip the POST.
                    coordinator.hass.config_entries.async_update_entry(
                        coordinator._entry,
                        data={
                            **coordinator._entry.data,
                            "fcm_registered_token": coordinator._fcm_token,
                            "fcm_registered_device_type": "ANDROID",
                            "fcm_registered_at": time.time(),
                        },
                    )
                    _LOGGER.debug(
                        "FCM: token already registered with Bosch (HTTP 500 sh:internal.error) — skipping on next restart"
                    )
                    return True
                _LOGGER.warning(
                    "FCM token registration failed: HTTP %d — %s",
                    resp.status,
                    resp_body[:200],
                )
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.warning("FCM token registration error: %s", err)
    return False


async def async_stop_fcm_push(coordinator: Any) -> None:
    """Stop the FCM push listener.

    firebase-messaging's ``client.stop()`` cancels its internal read/heartbeat
    tasks via ``task.cancel()`` but returns before those tasks finish their
    ``finally: await self._do_writer_close()`` cleanup. If we recreate the
    FcmPushClient before the old SSL shutdown completes (e.g. user toggles
    ``fcm_push_mode`` in the UI), the old read loop emits
    ``ERROR [firebase_messaging.fcmpushclient] Unexpected exception during read``
    once per ~63 s and never recovers — the state machine sees the SSL close
    fire outside of ``RESETTING`` state. Awaiting the cancelled tasks here
    drains the old SSL session before the new client starts. Library has no
    documented stop-and-restart pattern (upstream issues #23, #33 open).
    """
    with coordinator._fcm_lock:
        client = coordinator._fcm_client
        running = coordinator._fcm_running
    if client and running:
        try:
            await client.stop()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.debug("FCM stop raised: %s", err)
        pending = getattr(client, "tasks", None) or []
        if pending:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=10.0,
                )
            except TimeoutError:
                _LOGGER.debug(
                    "FCM stop: %d background task(s) did not drain in 10 s — "
                    "proceeding (residual SSL close may log one final error)",
                    len(pending),
                )
            except asyncio.CancelledError:
                raise
        with coordinator._fcm_lock:
            coordinator._fcm_running = False
            coordinator._fcm_healthy = False
            coordinator._fcm_client = None
            coordinator._fcm_push_mode = "unknown"
        _LOGGER.info("FCM push listener stopped")


async def _async_run_fcm_supervisor(coordinator: Any) -> None:
    """FCM supervisor loop — keeps the push listener alive indefinitely.

    Replaces the watchdog + self-heal state machine. This task runs for the
    entire lifetime of the HA config entry. On each iteration it:
      1. Decides whether a hard-heal (credential purge + fresh registration)
         is needed (delivery-death flag, 3+ consecutive soft-only restarts,
         or PHONE_REGISTRATION_ERROR in the creds-staleness window).
      2. Starts the FCM listener inside the start-lock.
      3. Polls `is_started()` every FCM_SUPERVISOR_POLL_SEC seconds.
      4. When the listener dies, waits FCM_SUPERVISOR_BACKOFF_SEC[failures]
         before the next attempt (resets to 0 if a real push arrived).

    Root-cause context (2026-06-25): `firebase-messaging 0.4.5` bug #33
    causes the listener to terminate permanently after SSL timeout / 3
    sequential errors. PR #36 (merged main, not yet on PyPI) fixes this.
    The supervisor ensures recovery regardless of library version.
    """
    failures = 0  # consecutive restarts WITHOUT a push received
    soft_streak = 0  # consecutive soft-only restarts (no hard-heal between)

    _LOGGER.debug("FCM supervisor started")

    while True:
        push_ts_before = coordinator._fcm_last_push

        # ── Decide heal strategy ────────────────────────────────────────────
        force_hard = getattr(coordinator, "_fcm_force_hard_heal", False)
        needs_hard = (
            force_hard
            or soft_streak >= FCM_SUPERVISOR_SOFT_HEAL_MAX
            or get_recent_fcm_creds_staleness_count(600.0) > 0
            or not coordinator._entry.data.get("fcm_credentials")
        )

        if force_hard:
            coordinator._fcm_force_hard_heal = False

        if needs_hard:
            if force_hard:
                reason = "polling confirmed delivery dead"
            elif soft_streak >= FCM_SUPERVISOR_SOFT_HEAL_MAX:
                reason = (
                    f"{soft_streak} soft-restarts without a push — delivery likely dead"
                )
            elif get_recent_fcm_creds_staleness_count(600.0) > 0:
                reason = "PHONE_REGISTRATION_ERROR in last 10 min — creds stale"
            else:
                reason = "no persisted credentials"
            _LOGGER.info("FCM supervisor: hard-heal (%s) — purging credentials", reason)

            try:
                async with coordinator._fcm_start_lock:
                    await async_stop_fcm_push(coordinator)
                    new_data = {
                        k: v
                        for k, v in coordinator._entry.data.items()
                        if not k.startswith("fcm_")
                    }
                    purged = sorted(set(coordinator._entry.data) - set(new_data))
                    coordinator.hass.config_entries.async_update_entry(
                        coordinator._entry, data=new_data
                    )
                    _LOGGER.info(
                        "FCM supervisor: purged %d entry-data keys: %s",
                        len(purged),
                        purged,
                    )
                reset_fcm_creds_staleness_counter()
                soft_streak = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                # An unhandled exception here (e.g. from async_update_entry)
                # used to propagate straight out of this loop, killing the
                # entire supervisor task — FCM push then stayed fully down
                # until the next coordinator-tick watchdog cycle noticed
                # sup.done() and restarted it, instead of the designed ~10s
                # poll cadence (bug-hunt 2026-07-03). Log and retry instead.
                _LOGGER.exception(
                    "FCM supervisor: hard-heal purge raised an exception — "
                    "retrying next iteration"
                )
                try:
                    await asyncio.sleep(FCM_SUPERVISOR_BACKOFF_SEC[0])
                except asyncio.CancelledError:
                    break
                continue

        # ── Start listener ─────────────────────────────────────────────────
        started = False
        try:
            lock = getattr(coordinator, "_fcm_start_lock", None)
            if lock is None:
                lock = asyncio.Lock()
                coordinator._fcm_start_lock = lock
            async with lock:
                started = await _async_start_fcm_push_locked(coordinator)
        except asyncio.CancelledError:
            _LOGGER.debug("FCM supervisor cancelled during start")
            break
        except Exception:
            _LOGGER.exception("FCM supervisor: listener start raised exception")

        if not started:
            failures += 1
            soft_streak += 1
            delay = FCM_SUPERVISOR_BACKOFF_SEC[
                min(failures - 1, len(FCM_SUPERVISOR_BACKOFF_SEC) - 1)
            ]
            _LOGGER.info(
                "FCM supervisor: start failed — retry in %.0fs (attempt #%d)",
                delay,
                failures,
            )
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            continue

        # ── Listener running — poll until it dies ──────────────────────────
        _LOGGER.debug(
            "FCM supervisor: listener up — polling every %.0fs", FCM_SUPERVISOR_POLL_SEC
        )
        forced_heal = False
        try:
            while True:
                await asyncio.sleep(FCM_SUPERVISOR_POLL_SEC)
                fcm_client = coordinator._fcm_client
                if fcm_client is None or not fcm_client.is_started():
                    break
                if getattr(coordinator, "_fcm_force_hard_heal", False):
                    # Silent-delivery-death: the poll-based fallback detected a
                    # camera event FCM never delivered while is_started() still
                    # reports True. Break out NOW so the top-of-loop hard-heal
                    # fires promptly — otherwise the forced flag is only re-read
                    # once the client independently dies, which in this exact
                    # scenario (the whole reason the flag exists) may not happen
                    # for a long time, or ever. (bug-hunt 2026-07-01)
                    forced_heal = True
                    _LOGGER.info(
                        "FCM supervisor: forced hard-heal requested while listener "
                        "still reported started — restarting to purge credentials"
                    )
                    break
        except asyncio.CancelledError:
            await async_stop_fcm_push(coordinator)
            _LOGGER.debug("FCM supervisor: cancelled while listener was running")
            break
        except Exception:
            # Anything unexpected here (e.g. fcm_client.is_started() raising)
            # used to propagate straight out of _async_run_fcm_supervisor,
            # killing the task outright — recovery then depended on the
            # coordinator-tick watchdog noticing sup.done(), not the designed
            # ~10s poll cadence (bug-hunt 2026-07-03). Treat it the same as a
            # normal listener termination: fall through to the stop+backoff
            # logic below instead of dying silently.
            _LOGGER.exception(
                "FCM supervisor: exception while polling listener — "
                "treating as terminated"
            )

        if forced_heal:
            _LOGGER.info("FCM supervisor: listener stopped for forced hard-heal")
        else:
            _LOGGER.info("FCM supervisor: listener terminated (is_started()=False)")
        await async_stop_fcm_push(coordinator)

        # ── Choose backoff ─────────────────────────────────────────────────
        push_received = coordinator._fcm_last_push > push_ts_before
        if forced_heal:
            # A hard-heal was explicitly requested (delivery-death watchdog).
            # Restart fast so the top-of-loop credential purge happens promptly
            # instead of sitting on an escalated backoff delay. The flag is left
            # set for the top of the loop to consume. (bug-hunt 2026-07-01)
            delay = FCM_SUPERVISOR_BACKOFF_SEC[0]
            _LOGGER.info(
                "FCM supervisor: applying forced hard-heal — fast restart in %.0fs",
                delay,
            )
        elif push_received:
            # Listener was delivering — transient drop; fast restart, reset counters.
            failures = 0
            soft_streak = 0
            delay = FCM_SUPERVISOR_BACKOFF_SEC[0]
            _LOGGER.info(
                "FCM supervisor: transient drop (had pushes) — fast restart in %.0fs",
                delay,
            )
        else:
            failures += 1
            soft_streak += 1
            delay = FCM_SUPERVISOR_BACKOFF_SEC[
                min(failures - 1, len(FCM_SUPERVISOR_BACKOFF_SEC) - 1)
            ]
            _LOGGER.info(
                "FCM supervisor: no pushes since last start — retry in %.0fs "
                "(failure #%d, soft streak %d/%d)",
                delay,
                failures,
                soft_streak,
                FCM_SUPERVISOR_SOFT_HEAL_MAX,
            )

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            break

    _LOGGER.debug("FCM supervisor stopped")


async def _async_persist_fcm_creds(coordinator: Any, creds: dict[str, Any]) -> None:
    """Write FCM credentials into the config entry (must run in event loop)."""
    try:
        coordinator.hass.config_entries.async_update_entry(
            coordinator._entry,
            data={**coordinator._entry.data, "fcm_credentials": creds},
        )
        _LOGGER.debug("FCM credentials saved to config entry")
    except Exception as err:
        _LOGGER.debug("FCM creds persist failed: %s", err)


# ── FCM push callback ───────────────────────────────────────────────────────


def _on_fcm_push(
    coordinator: Any, notification: dict[str, Any], persistent_id: str, obj: Any = None
) -> None:
    """Called when a push notification arrives from Bosch CBS.

    The push is a silent wake-up signal with no event payload.
    We immediately trigger an event fetch + snapshot refresh for all cameras.
    """
    with coordinator._fcm_lock:
        # Drop pushes that arrive after async_stop_fcm_push cleared the client —
        # a trailing push would otherwise reschedule async_handle_fcm_push on a
        # loop that already considers FCM down.
        if not coordinator._fcm_running:
            return
        coordinator._fcm_last_push = time.monotonic()
        coordinator._fcm_healthy = True
    _LOGGER.info(
        "FCM push received (id=%s, from=%s) — fetching events",
        persistent_id,
        notification.get("from", "?"),
    )

    # Schedule immediate event fetch + snapshot refresh on the HA event loop.
    # Create + track the task INSIDE the threadsafe callback so it holds a strong
    # reference in _bg_tasks — an untracked task can be GC-cancelled mid-flight on
    # shutdown, leaving coordinator.data partially updated.
    def _spawn_fcm_handler() -> None:
        _t = coordinator.hass.async_create_task(async_handle_fcm_push(coordinator))
        coordinator._bg_tasks.add(_t)
        _t.add_done_callback(coordinator._bg_tasks.discard)

    coordinator.hass.loop.call_soon_threadsafe(_spawn_fcm_handler)


async def async_handle_fcm_push(coordinator: Any, _attempt: int = 0) -> None:
    """Handle an FCM push — fetch fresh events for all cameras and fire HA events.

    Bosch's FCM push can beat its own /v11/events cloud index by a few seconds:
    the first fetch then returns no new event, and the alert would otherwise only
    arrive via the ~300 s safety poll ("alles über das normale pull verhalten").
    When a push finds nothing new, this handler retries a couple of times with a
    short backoff (`_attempt`) so the event is caught within seconds. Dedup via
    _alert_sent_ids + _last_event_ids makes a re-scan safe (no double alerts).
    """
    token = coordinator.token
    if not token or not coordinator.data:
        # Race: FCM push can arrive during setup, before the first coordinator
        # refresh has populated .data. Without this guard we crash with
        # `AttributeError: 'NoneType' object has no attribute 'keys'`.
        return

    session = await async_get_bosch_cloud_session(coordinator.hass)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    _dispatched_new = False
    _any_fetch_ok = False  # B1 fix: track if ≥1 camera fetch returned HTTP 200
    for cam_id in list(coordinator.data.keys()):
        try:
            url = f"{CLOUD_API}/v11/events?videoInputId={cam_id}&limit=5"
            async with asyncio.timeout(10):
                async with session.get(url, headers=headers) as r:
                    if r.status != 200:
                        continue
                    events = await r.json()
            _any_fetch_ok = True  # HTTP 200 received — cloud is reachable

            if not events:
                continue

            newest_id = events[0].get("id", "")
            prev_id = coordinator._last_event_ids.get(cam_id)

            # Per-event-ID dedup: concurrent FCM handlers (Bosch sometimes
            # sends two pushes ~10 s apart for the same event) otherwise both
            # pass the prev_id check and fire two alert chains.
            _now = time.monotonic()
            _sent = coordinator._alert_sent_ids
            if newest_id and _sent.get(newest_id, float("-inf")) > _now - 60.0:
                _LOGGER.debug(
                    "FCM push dedup: skipping duplicate alert for %s id=%s (already sent %.1fs ago)",
                    cam_id,
                    newest_id[:8],
                    _now - _sent[newest_id],
                )
                continue
            # Evict entries older than 120s on every call. Original
            # `if len(_sent) > 32` guard could starve eviction during
            # burst-event scenarios (4 cams × dense events all within
            # 120 s window → cache grows past 32 but eviction loop finds
            # nothing to evict, so it grows unbounded). Plain age-based
            # cleanup on every call has O(len) cost which is fine — len
            # stays small.
            # NOTE: _sent aliases coordinator._alert_sent_ids — must mutate it
            # IN PLACE (a dict-comprehension rebind would detach the alias and
            # lose every later write at `_sent[newest_id] = _now`). Single-pass
            # collect-then-pop keeps the shared dict intact.
            if _sent:
                _cutoff = _now - 120.0
                for _k in [k for k, v in _sent.items() if v < _cutoff]:
                    del _sent[_k]

            if prev_id is not None and newest_id and newest_id != prev_id:
                _dispatched_new = True
                # Record alert dispatch ASAP so a concurrent handler sees it
                _sent[newest_id] = _now
                # Update last event ID FIRST to prevent polling from
                # detecting the same event and sending duplicate alerts
                coordinator._last_event_ids[cam_id] = newest_id

                newest_event = events[0]
                event_type = newest_event.get("eventType", "")
                event_tags = newest_event.get("eventTags", []) or []
                cam_name = (
                    coordinator.data.get(cam_id, {})
                    .get("info", {})
                    .get("title", cam_id)
                )

                # Gen2 cameras (Outdoor II w/ DualRadar, Indoor II) send
                # eventType=MOVEMENT with eventTags=["PERSON"] when a human is
                # detected — the tag is more specific than the type, so upgrade.
                # Confirmed 2026-04-11 via /v11/events on Terrasse: 15x tags=['PERSON'].
                if "PERSON" in event_tags and event_type == "MOVEMENT":
                    event_type = "PERSON"

                _LOGGER.info(
                    "FCM push -> new %s event for %s (id=%s, tags=%s)",
                    event_type,
                    cam_name,
                    newest_id[:8],
                    event_tags,
                )

                # Update cached events (next coordinator tick rebuilds data[]).
                coordinator._cached_events[cam_id] = events
                # Mirror into coordinator.data so the windowed binary sensors
                # (motion/person/audio in binary_sensor.py) see the new event
                # immediately on the async_update_listeners() call below —
                # otherwise data[] is only refreshed on the next tick (up to
                # scan_interval seconds away), by which time the event may be
                # outside EVENT_ACTIVE_WINDOW and the sensor stays OFF.
                if cam_id in coordinator.data:
                    coordinator.data[cam_id]["events"] = events

                # Fire HA event bus
                event_payload = {
                    "camera_id": cam_id,
                    "camera_name": cam_name,
                    "timestamp": newest_event.get("timestamp", ""),
                    "image_url": newest_event.get("imageUrl", ""),
                    "event_id": newest_id,
                    "source": "fcm_push",
                }
                if event_type == "MOVEMENT":
                    coordinator.hass.bus.async_fire(
                        "bosch_shc_camera_motion", event_payload
                    )
                elif event_type == "AUDIO_ALARM":
                    coordinator.hass.bus.async_fire(
                        "bosch_shc_camera_audio_alarm", event_payload
                    )
                elif event_type == "PERSON":
                    coordinator.hass.bus.async_fire(
                        "bosch_shc_camera_person", event_payload
                    )

                # Mini-NVR event_buffered clip assembly (issue #43 follow-up,
                # realKim-dotcom): on a movement/person event for a camera in
                # event_buffered mode with the NVR switch ON and LOCAL, assemble
                # the pre-roll(+post-roll) clip and drop it into the NVR staging
                # tree so the existing drain watcher ships it. Independent of the
                # notification switches below — a user may want clips without
                # push alerts (or vice versa).
                #
                # Defensive against minimal test-fixture coordinators (no
                # `__init__`) that don't define `get_nvr_mode` — mirrors the
                # `_is_rcp_lan_denied` pattern elsewhere in this integration:
                # treat "no Mini-NVR support on this stub" as "nothing to do"
                # rather than raising.
                _get_nvr_mode = getattr(coordinator, "get_nvr_mode", None)
                if (
                    event_type in ("MOVEMENT", "PERSON")
                    and callable(_get_nvr_mode)
                    and _get_nvr_mode(cam_id) == "event_buffered"
                ):
                    _nvr_opts = coordinator.options
                    if (
                        _nvr_opts.get("enable_nvr")
                        and (
                            int(_nvr_opts.get("nvr_preroll_seconds") or 0) > 0
                            or int(_nvr_opts.get("nvr_postroll_seconds") or 0) > 0
                        )
                    ) and should_record(
                        coordinator,
                        cam_id,
                        switch_on=coordinator._nvr_user_intent.get(cam_id, False),
                    ):
                        _clip_task = coordinator.hass.async_create_task(
                            assemble_and_ship_motion_clip(coordinator, cam_id)
                        )
                        coordinator._bg_tasks.add(_clip_task)
                        _clip_task.add_done_callback(coordinator._bg_tasks.discard)

                # Check notification switches before sending alert.
                # Master switch (switch.bosch_{name}_notifications) must be ON,
                # AND the type-specific switch must be ON for this event type.
                _alert_blocked = False
                _base = (
                    cam_name.lower()
                    .replace(" ", "_")
                    .replace("ä", "ae")
                    .replace("ö", "oe")
                    .replace("ü", "ue")
                )
                _master_eid = f"switch.bosch_{_base}_notifications"
                _master_state = coordinator.hass.states.get(_master_eid)
                if _master_state and _master_state.state == "off":
                    _LOGGER.debug("Alert suppressed: %s is OFF", _master_eid)
                    _alert_blocked = True
                # Type-specific check
                # Map raw event types to the notification-switch slug used by
                # BoschNotificationTypeSwitch (switch.bosch_{base}_{slug}_notifications).
                # TROUBLE_CONNECT + TROUBLE_DISCONNECT both follow the `trouble` switch —
                # they're system events and can be silenced together without affecting
                # motion/person alerts.
                _type_map = {
                    "MOVEMENT": "movement",
                    "PERSON": "person",
                    "AUDIO_ALARM": "audio",
                    "CAMERA_ALARM": "camera_alarm",
                    "TROUBLE": "trouble",
                    "TROUBLE_CONNECT": "trouble",
                    "TROUBLE_DISCONNECT": "trouble",
                }
                _type_key = _type_map.get(event_type)
                if _type_key and not _alert_blocked:
                    _type_eid = f"switch.bosch_{_base}_{_type_key}_notifications"
                    _type_state = coordinator.hass.states.get(_type_eid)
                    if _type_state and _type_state.state == "off":
                        _LOGGER.debug("Alert suppressed: %s is OFF", _type_eid)
                        _alert_blocked = True

                if not _alert_blocked:
                    # Send alert notification (3-step: text + snapshot + video).
                    # Track in _bg_tasks: async_send_alert runs ~minutes (image
                    # retries + clip poll/download); an untracked task can be
                    # GC-cancelled mid-flight on shutdown, leaving partial files.
                    _alert_task = coordinator.hass.async_create_task(
                        async_send_alert(
                            coordinator,
                            cam_name,
                            event_type,
                            newest_event.get("timestamp", ""),
                            newest_event.get("imageUrl", ""),
                            newest_event.get("videoClipUrl", ""),
                            newest_event.get("videoClipUploadStatus", ""),
                            event_id=newest_id,
                            cam_id=cam_id,
                        )
                    )
                    coordinator._bg_tasks.add(_alert_task)
                    _alert_task.add_done_callback(coordinator._bg_tasks.discard)
                else:
                    _LOGGER.info(
                        "Alert skipped for %s (%s) — notifications disabled",
                        cam_name,
                        event_type,
                    )

                # Path A — live-snap refresh: fire immediately on every real event so
                # the frontend gets a fresh camera frame within ~1-2 s of the event.
                # _SNAP_EVENT_TYPES (module-level) excludes status-only types.
                # WHY tracked: fire-and-forget tasks get GC-collected on HA shutdown
                # mid-flight, leaving half-written temp files. Strong reference +
                # discard callback allows async_unload_entry to cancel+await cleanly.
                cam_entity = coordinator._camera_entities.get(cam_id)
                if cam_entity and event_type in _SNAP_EVENT_TYPES:
                    # Stream-contention guard: while the RTSP live-stream is active,
                    # Path A's live-snap refresh (PUT /connection + snap.jpg) competes
                    # with the RTSP OPTIONS keepalive on the camera's single TLS
                    # control channel.  On Gen2 the 30-s RTSP session timeout means
                    # a delayed OPTIONS response (>30 s) tears down the producer →
                    # 5–10 s stream freeze.  Path B (alert step-2 in async_send_alert)
                    # already pushes the Bosch event image (with AI overlay) into
                    # _cached_image via the same cloud session that fetches the
                    # notification snapshot — no extra camera-side TLS request needed.
                    # Skip Path A entirely when is_streaming=True; Path B is sufficient.
                    # Source: knowledge-base/stream-freeze-on-motion-event-contention.md
                    if getattr(cam_entity, "is_streaming", False):
                        _LOGGER.debug(
                            "FCM Path A: skipped for %s (%s) — camera is streaming, "
                            "Path B will update cache",
                            cam_name,
                            event_type,
                        )
                    else:
                        try:
                            # Per-model settle delay — Gen2 captures immediately (0 s),
                            # Gen1 needs ~1.5 s so the snap reflects the post-trigger frame.
                            from .models import get_model_config

                            hw_cache = getattr(coordinator, "_hw_version", {})
                            hw = (
                                hw_cache.get(cam_id, "")
                                if hasattr(hw_cache, "get")
                                else ""
                            )
                            refresh_delay = get_model_config(hw).event_refresh_delay
                            task = coordinator.hass.async_create_task(
                                cam_entity._async_trigger_image_refresh(
                                    delay=refresh_delay
                                )
                            )
                            coordinator._bg_tasks.add(task)
                            task.add_done_callback(coordinator._bg_tasks.discard)
                            _LOGGER.debug(
                                "FCM Path A: live-snap refresh scheduled for %s (%s, delay=%.1fs)",
                                cam_name,
                                event_type,
                                refresh_delay,
                            )
                        except Exception as _snap_err:
                            _LOGGER.warning(
                                "FCM Path A: failed to schedule live-snap refresh for %s: %s",
                                cam_name,
                                _snap_err,
                            )

                # Notify all entity listeners
                coordinator.async_update_listeners()

                # Mark new event as read on the Bosch cloud (gated by user option).
                # BUG-4 fix: fire-and-forget via async_create_task so cameras
                # 2/3/4 are not blocked for up to 5s by camera 1's mark-read
                # HTTP PUT inside the per-cam loop.
                if coordinator.options.get("mark_events_read", False):

                    async def _mark_read_bg(
                        _coord: Any = coordinator, _eid: str = newest_id
                    ) -> None:
                        try:
                            await async_mark_events_read(_coord, [_eid])
                        except Exception:  # noqa: S110 # best-effort cloud housekeeping
                            pass

                    _mr_task = coordinator.hass.async_create_task(_mark_read_bg())
                    coordinator._bg_tasks.add(_mr_task)
                    _mr_task.add_done_callback(coordinator._bg_tasks.discard)

            elif newest_id:
                coordinator._last_event_ids[cam_id] = newest_id

        except (TimeoutError, aiohttp.ClientError) as err:
            # Transient cloud hiccup — the retry/backoff loop below (and the
            # 300 s safety poll) recover from it without operator action.
            # → DEBUG, not WARNING.
            _LOGGER.debug("FCM push event fetch network error for %s: %s", cam_id, err)
        except Exception as err:
            _LOGGER.debug("FCM push event fetch error for %s: %s", cam_id, err)

    # Push beat the cloud index → no new event this pass. Retry a couple of
    # times with a short backoff before falling back to the 300 s safety poll.
    # B1 fix: only retry when ≥1 fetch succeeded (HTTP 200) — if ALL cameras
    # failed with TimeoutError/ClientError the cloud endpoint is down and
    # retrying wastes round-trips + adds 2+4 s of sleep on a dead endpoint.
    _FCM_FETCH_RETRY_BACKOFFS = (2.0, 4.0)
    if (
        not _dispatched_new
        and _any_fetch_ok
        and _attempt < len(_FCM_FETCH_RETRY_BACKOFFS)
    ):
        await asyncio.sleep(_FCM_FETCH_RETRY_BACKOFFS[_attempt])
        if getattr(coordinator, "_fcm_running", False):
            await async_handle_fcm_push(coordinator, _attempt + 1)


# ── Alert routing helpers ────────────────────────────────────────────────────


def get_alert_services(coordinator: Any, type_key: str) -> list[str]:
    """Return notify services for a given alert type key.

    "system" and "information" fall back to alert_notify_service when empty.
    "screenshot" and "video" do NOT fall back — empty means skip that step.
    type_key: "system" | "information" | "screenshot" | "video"
    """
    opts = coordinator.options
    raw = opts.get(f"alert_notify_{type_key}", "").strip()
    if not raw and type_key not in ("screenshot", "video"):
        raw = opts.get("alert_notify_service", "").strip()
    return [s.strip() for s in raw.split(",") if s.strip()]


def build_notify_data(
    svc: str,
    message: str,
    file_path: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Build notify service call data with correct attachment format per service type.

    mobile_app (iOS + Android HA Companion): image served from /local/bosch_alerts/
    telegram_bot: uses photo field
    All others (Signal, email, ...): file path in data.attachments
    """
    data: dict[str, Any] = {"message": message}
    if title:
        data["title"] = title
    if not file_path:
        return data
    fname = os.path.basename(file_path)
    if "mobile_app" in svc:
        # HA Companion App — image URL served without auth from /config/www/
        # Files deleted within seconds when alert_delete_after_send=True
        notify_data: dict[str, Any] = {
            "image": f"/local/bosch_alerts/{fname}",
            "push": {"sound": "default"},  # iOS: play sound; Android ignores this key
        }
        data["data"] = notify_data
    elif "telegram" in svc.lower():
        data["data"] = {"photo": file_path, "caption": message}
    else:
        # Signal, email, generic — local file path attachment
        data["data"] = {"attachments": [file_path]}
    return data


def _write_file(path: str, data: bytes) -> None:
    """Write binary data to a file (runs in executor)."""
    with open(path, "wb") as f:
        f.write(data)


# ── 3-step alert pipeline ───────────────────────────────────────────────────


async def async_send_alert(
    coordinator: Any,
    cam_name: str,
    event_type: str,
    timestamp: str,
    image_url: str,
    clip_url: str = "",
    clip_status: str = "",
    event_id: str = "",
    cam_id: str = "",
) -> None:
    """Send a 3-step alert: instant text, snapshot image, video clip.

    Step 1: Immediate text notification (no delay)
    Step 2: Download snapshot from Bosch cloud (after 5s), send with image
    Step 3: Download video clip (after 15s total), send as attachment

    cam_id: stable camera ID (UUID). When provided, all sub-lookups use it
    directly instead of searching coordinator.data by the mutable title string.
    Callers that cannot supply cam_id (legacy / __init__ wrapper) leave it as
    "" and the title-fallback is used instead.
    """
    from .smb import sync_local_save, sync_smb_upload

    # Bosch has been observed sending "timestamp": null in event payloads;
    # newest_event.get("timestamp", "") only substitutes the default when the
    # key is ABSENT, not when its value is JSON null, so a bare None could
    # reach here and crash len(timestamp)/timestamp[:19] below. This runs
    # inside an untracked-by-caller hass.async_create_task, so an unguarded
    # TypeError here was silently swallowed by asyncio's default exception
    # handler — the HA event bus fired fine, but the text/snapshot/clip
    # notification steps never ran, with no visible symptom (bug-hunt
    # 2026-07-03).
    timestamp = timestamp or ""

    opts = coordinator.options

    # Resolve the stable cam_id once at push-receipt time (start of coroutine).
    # Doing this early ensures all sub-lookups (Path B, Step 3, AI title-match)
    # use the stable ID rather than the mutable display title — fixes B04-BUG-2
    # and W-imageflip-BUG-2 (stale privacy / wrong cam on rename).
    _resolved_cam_id: str | None = cam_id if cam_id else None
    if not _resolved_cam_id:
        for _cid, _cdata in coordinator.data.items():
            if _cdata.get("info", {}).get("title", "") == cam_name:
                _resolved_cam_id = _cid
                break

    # Capture privacy state NOW (at push-receipt time, start of coroutine).
    # Path B runs up to ~30 s later; re-reading the live cache at that point
    # can pick up a post-privacy-off value and write a pre-privacy frame into
    # the cache — fixing W-imageflip-BUG-2.
    _shc_cache_early = getattr(coordinator, "_shc_state_cache", {})
    _push_time_priv: bool = (
        _shc_cache_early.get(_resolved_cam_id, {}).get("privacy_mode", False)
        if _resolved_cam_id
        else False
    )

    # Per-type service routing: information/screenshot/video each fall back to alert_notify_service.
    # TROUBLE events use "system" — check that before bailing on missing information services.
    _is_trouble = event_type in ("TROUBLE_CONNECT", "TROUBLE_DISCONNECT")
    info_svcs = get_alert_services(coordinator, "information")
    _has_local_save = bool(opts.get("enable_local_save") and opts.get("download_path"))
    _has_smb_upload = bool(opts.get("enable_smb_upload") and opts.get("smb_server"))
    if (
        not info_svcs
        and not _is_trouble
        and not _has_local_save
        and not _has_smb_upload
    ):
        return  # Nothing to do (no notifications, no local save, no SMB upload)

    save_snapshots = opts.get("alert_save_snapshots", False)
    delete_after = opts.get("alert_delete_after_send", True)
    ts_short = timestamp[11:19] if len(timestamp) >= 19 else timestamp

    # Event type → German label + emoji icon.
    # Derived from full mitmproxy capture analysis (116K+ events across 12 captures,
    # 2026-04-11): 5 unique (eventType, eventTags) combinations observed.
    # Key finding: PERSON events are eventType=MOVEMENT + eventTags=["PERSON"] (Gen2
    # DualRadar) — the caller is expected to have already upgraded event_type from
    # "MOVEMENT" to "PERSON" when tag is present (see __init__.py + fcm.py push path).
    type_label = {
        "MOVEMENT": "Bewegung",
        "PERSON": "Person erkannt",
        "AUDIO_ALARM": "Audio-Alarm",
        "TROUBLE_CONNECT": "Verbindung hergestellt",
        "TROUBLE_DISCONNECT": "Verbindung getrennt",
        "CAMERA_ALARM": "Kamera-Alarm",
    }.get(event_type, event_type)
    type_icon = {
        "MOVEMENT": "\U0001f4f7",  # 📷
        "PERSON": "\U0001f9d1",  # 🧑
        "AUDIO_ALARM": "\U0001f50a",  # 🔊
        "TROUBLE_CONNECT": "\U0001f7e2",  # 🟢
        "TROUBLE_DISCONNECT": "\U0001f534",  # 🔴
        "CAMERA_ALARM": "\U0001f6a8",  # 🚨
    }.get(event_type, "\u26a0\ufe0f")  # ⚠️ fallback

    # www/bosch_alerts/ is served as /local/bosch_alerts/ — needed for mobile_app notifications
    alert_dir = os.path.join(coordinator.hass.config.config_dir, "www", "bosch_alerts")
    await coordinator.hass.async_add_executor_job(os.makedirs, alert_dir, 0o755, True)
    ts_safe = timestamp[:19].replace(":", "-").replace("T", "_")
    session = await async_get_bosch_cloud_session(coordinator.hass)
    headers = {"Authorization": f"Bearer {coordinator.token}", "Accept": "*/*"}
    files_to_cleanup: list[str] = []
    # Snapshot bytes captured in step 2 — passed to SMB/FTP upload so the
    # upload can use the already-in-memory bytes instead of re-downloading
    # from Bosch cloud (which would contend with the RTSP live-stream's TLS
    # control channel).  None until step 2 successfully downloads the image.
    _prefetched_snapshot: bytes | None = None

    async def _notify_type(
        type_key: str, message: str, file_path: str | None = None
    ) -> None:
        """Send to services configured for this alert type (information/screenshot/video)."""
        for svc in get_alert_services(coordinator, type_key):
            try:
                domain, service = svc.split(".", 1)
                call_data = build_notify_data(svc, message, file_path)
                await coordinator.hass.services.async_call(domain, service, call_data)
            except Exception as err:
                _LOGGER.warning("Alert send failed for %s (%s): %s", svc, type_key, err)

    # -- Step 1: Instant text alert ----------------------------------------
    # TROUBLE_CONNECT/DISCONNECT are connectivity events — route to "system",
    # not "information", and skip snapshot/clip steps (no media for these).
    _step1_key = "system" if _is_trouble else "information"
    try:
        await _notify_type(
            _step1_key, f"{type_icon} {cam_name}: {type_label} ({ts_short})"
        )
        _LOGGER.debug("Alert step 1 (text) sent via %s", _step1_key)
    except Exception as err:
        _LOGGER.warning("Alert step 1 failed: %s", err)
        return

    if _is_trouble:
        return  # No snapshot/clip for connectivity events

    # -- Step 2: Snapshot image (after 3s, retries up to ~25s) ------------
    # The FCM push sometimes arrives before Bosch's event API has the imageUrl
    # populated. Single re-fetch at 5s missed slow-cloud events (observed
    # 2026-04-26: text alert sent, snapshot silently skipped, JPG only
    # appeared 90s later via the SMB upload path). Retry at +3 / +10 / +25 s
    # cumulative — covers steady-state cloud and warm-up cases without
    # delaying the common path noticeably.
    #
    # BUG-5 fix: track whether image_url was empty at push-arrival time.
    # The 5s sleep before downloading is only needed when the URL was missing
    # on push arrival (retry loop already introduces cumulative delays for that
    # case, so the extra sleep is for the "URL present from the start" path only
    # — but it's unnecessary there too since Bosch's image is already ready if
    # the URL was provided). Move the sleep inside the empty-URL branch so the
    # fast path (URL known upfront) skips the 5s stall entirely.
    _image_url_was_empty = not image_url
    if _image_url_was_empty:
        # Use the stable cam_id resolved at push-receipt time (B04-BUG-2 fix).
        # Querying with an empty videoInputId returns EVERY camera's events and
        # event[0] would attach a foreign camera's image to this alert.
        events_url = (
            f"{CLOUD_API}/v11/events?videoInputId={_resolved_cam_id}&limit=5"
            if _resolved_cam_id
            else None
        )
        if events_url is None:
            _LOGGER.debug(
                "Alert: no camera matches title %r — skipping image re-fetch",
                cam_name,
            )
        for attempt, delay in enumerate((3, 7, 15), start=1):
            if events_url is None:
                break
            await asyncio.sleep(delay)
            try:
                async with asyncio.timeout(10):
                    async with session.get(events_url, headers=headers) as r:
                        if r.status == 200:
                            fresh_events = await r.json()
                            if fresh_events:
                                image_url = fresh_events[0].get("imageUrl", "")
                                clip_url = (
                                    fresh_events[0].get("videoClipUrl", "") or clip_url
                                )
                                clip_status = (
                                    fresh_events[0].get("videoClipUploadStatus", "")
                                    or clip_status
                                )
            except Exception as err:
                _LOGGER.debug("Alert: re-fetch attempt %d failed: %s", attempt, err)
                continue
            if image_url:
                _LOGGER.debug("Alert: re-fetched image_url on attempt %d", attempt)
                break
        if not image_url:
            _LOGGER.debug(
                "Alert: image_url still empty after 3 retries — skipping step 2"
            )

    # Reject an unsafe imageUrl BEFORE the download block so a rejected URL can
    # never reach session.get() (previously it set image_url="" but still fell
    # through to attempt the fetch with an empty URL).
    if image_url and not _is_safe_bosch_url(image_url):
        _LOGGER.warning("Alert: unsafe imageUrl rejected: %s", image_url[:60])
        image_url = ""

    if image_url:
        # Only wait when the URL was missing at push time and had to be
        # re-fetched — in that case the retry loop already slept up to 25 s,
        # but a brief extra settle avoids a race where Bosch's image is still
        # being finalized after the URL first appears.  When the URL was
        # provided with the original push the image is already ready and the
        # sleep is a pure 5 s stall with no benefit (BUG-5 fix).
        if _image_url_was_empty:
            await asyncio.sleep(2)
        # Neutralise path traversal: cam_name is the cloud-provided camera title
        # and must never escape alert_dir (e.g. a title like "../../config/secrets").
        # ts_safe and event_type are integration-generated, but sanitise defensively.
        snap_path = os.path.join(
            alert_dir,
            f"{_safe_path_segment(cam_name)}_{_safe_path_segment(ts_safe)}"
            f"_{_safe_path_segment(event_type)}.jpg",
        )
        try:
            async with asyncio.timeout(15):
                async with session.get(image_url, headers=headers) as resp:
                    _snap_content_type = resp.headers.get("Content-Type", "")
                    if resp.status != 200 or "image" not in _snap_content_type:
                        # No else-branch below (the 200+image body is large and
                        # deeply nested) — log here instead so an expired/404/
                        # 410 snapshot URL doesn't skip step 2 with zero trace,
                        # making delivery failures undiagnosable (bug-hunt
                        # 2026-07-03).
                        _LOGGER.debug(
                            "Alert step 2 (screenshot) skipped for %s: HTTP %s "
                            "content-type=%r",
                            cam_name,
                            resp.status,
                            _snap_content_type,
                        )
                    if resp.status == 200 and "image" in _snap_content_type:
                        data = await resp.read()
                        if data:
                            # Capture bytes for SMB/FTP upload (avoid re-download).
                            _prefetched_snapshot = data
                            await coordinator.hass.async_add_executor_job(
                                _write_file, snap_path, data
                            )
                            caption = f"\U0001f4f8 {cam_name} Snapshot ({ts_short})"
                            # F2: optionally append an AI description of the
                            # snapshot to the push. Rate-limited + daily-budgeted
                            # in async_generate_ai_description; wrapped here so a
                            # failure can never break the screenshot notification.
                            if opts.get("ai_notify_include_description"):
                                try:
                                    # Use stable cam_id resolved at push-receipt
                                    # time (B04-BUG-2: title-match fails on rename).
                                    _ai_cid: str | None = _resolved_cam_id
                                    if _ai_cid:
                                        _desc = await coordinator.async_generate_ai_description(
                                            _ai_cid
                                        )
                                        if _desc:
                                            _desc = _desc[:200].rstrip()
                                            caption = f"{caption}\n\U0001f916 {_desc}"
                                except Exception as _ai_err:
                                    _LOGGER.debug(
                                        "AI notify-include failed: %s", _ai_err
                                    )
                            await _notify_type(
                                "screenshot",
                                caption,
                                snap_path,
                            )
                            _LOGGER.debug(
                                "Alert step 2 (screenshot) sent: %s", snap_path
                            )
                            if not save_snapshots:
                                files_to_cleanup.append(snap_path)

                            # Path B — push the Bosch event image (with AI overlay /
                            # motion box) into the camera entity cache so the image
                            # entity gets a second update ~5-30 s after Path A's snap.
                            #
                            # Fixes applied here:
                            #   W-imageflip-BUG-2: use _push_time_priv (captured at
                            #     coroutine start) instead of re-reading the live cache.
                            #     Re-reading can see privacy=False if privacy was turned
                            #     off after the event arrived, writing a pre-privacy
                            #     frame into cache.
                            #   B04-BUG-1: use byte-identity (_existing != data) not
                            #     byte-length (len mismatch) for dedup.  Same-length
                            #     different-content images (same scene, same quality)
                            #     would be incorrectly skipped with len comparison.
                            #   B04-BUG-2: use _resolved_cam_id (stable, push-time)
                            #     instead of title-lookup that fails on rename.
                            #
                            # Wrapped in try/except so any error here never affects
                            # the alert pipeline (cleanup, clip download, etc.).
                            try:
                                _cam_id_for_b: str | None = _resolved_cam_id
                                if _cam_id_for_b:
                                    _cam_entities = getattr(
                                        coordinator, "_camera_entities", {}
                                    )
                                    _cam_b = _cam_entities.get(_cam_id_for_b)
                                    # Use privacy state captured at push-receipt time
                                    # (W-imageflip-BUG-2 fix — not re-read from cache).
                                    if _cam_b and not _push_time_priv:
                                        _existing = _cam_b._cached_image
                                        # Byte-identity dedup (B04-BUG-1 fix):
                                        # len equality is NOT image equality.
                                        if _existing is None or _existing != data:
                                            _cam_b._cached_image = data
                                            _cam_b._last_image_fetch = time.monotonic()
                                            await save_snapshot(
                                                coordinator.hass, _cam_id_for_b, data
                                            )
                                            _img_entities = getattr(
                                                coordinator, "_image_entities", {}
                                            )
                                            _img_ent = _img_entities.get(_cam_id_for_b)
                                            if _img_ent is not None:
                                                await _img_ent.async_notify_refreshed()
                                            _LOGGER.debug(
                                                "FCM Path B: event image pushed to %s cache (%d B)",
                                                cam_name,
                                                len(data),
                                            )
                                        else:
                                            _LOGGER.debug(
                                                "FCM Path B: skipping %s — bytes identical (%d B)",
                                                cam_name,
                                                len(data),
                                            )
                            except Exception as _pb_err:
                                _LOGGER.warning(
                                    "FCM Path B: failed to update %s cache: %s",
                                    cam_name,
                                    _pb_err,
                                )
        except Exception as err:
            _LOGGER.warning("Alert step 2 failed: %s", err)

    # -- Step 3: Video clip — poll until ready, then download + send -------
    # Bosch uploads clips asynchronously. The event initially has
    # clip_status=Pending (or no clipUrl at all). We poll the events API
    # every 10s for up to 90s until videoClipUploadStatus=Done.
    # Use stable cam_id resolved at push-receipt time (B04-BUG-2 fix).
    _clip_cam_id: str | None = _resolved_cam_id

    if _clip_cam_id:
        # Neutralise path traversal: cam_name is the cloud-provided camera title
        # and must never escape alert_dir (e.g. a title like "../../config").
        # Mirrors the snapshot path guard above — the .mp4 write below
        # (_write_file) would otherwise honour a malicious title verbatim.
        clip_path = os.path.join(
            alert_dir,
            f"{_safe_path_segment(cam_name)}_{_safe_path_segment(ts_safe)}"
            f"_{_safe_path_segment(event_type)}.mp4",
        )
        auth_headers = {
            "Authorization": f"Bearer {coordinator.token}",
            "Accept": "application/json",
        }
        found_clip_url = clip_url if (clip_url and clip_status == "Done") else ""

        # Try direct clip.mp4 download first (faster than polling)
        if not found_clip_url:
            event_id = event_id or coordinator._last_event_ids.get(_clip_cam_id, "")
            if event_id:
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/events/{event_id}/clip.mp4",
                            headers={
                                "Authorization": f"Bearer {coordinator.token}",
                                "Accept": "*/*",
                            },
                        ) as r:
                            if r.status == 200 and "video" in r.headers.get(
                                "Content-Type", ""
                            ):
                                found_clip_url = (
                                    f"{CLOUD_API}/v11/events/{event_id}/clip.mp4"
                                )
                                _LOGGER.debug(
                                    "Alert: direct clip.mp4 available for %s", cam_name
                                )
                except Exception:  # noqa: S110 # best-effort HEAD probe for direct clip URL; failure falls through to poll path
                    pass

        if not found_clip_url and clip_status == "Unavailable":
            _LOGGER.debug(
                "Alert: clip status Unavailable from start — skipping poll for %s",
                cam_name,
            )
        elif not found_clip_url:
            # Poll for clip readiness (10s intervals, up to 90s)
            clip_unavailable = False
            for attempt in range(9):
                await asyncio.sleep(10)
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/events?videoInputId={_clip_cam_id}&limit=3",
                            headers=auth_headers,
                        ) as r:
                            if r.status != 200:
                                continue
                            fresh = await r.json()
                            for ev in fresh:
                                # Match by event_id (stable UUID) rather than
                                # timestamp[:19] — two events within the same
                                # second share the same prefix and the wrong
                                # clip could be attached (BUG-6 fix).
                                _ev_id = ev.get("id", "")
                                if event_id and _ev_id and _ev_id != event_id:
                                    continue
                                if not event_id and (
                                    (ev.get("timestamp") or "")[:19] != timestamp[:19]
                                ):
                                    # Fallback: no event_id known, use timestamp
                                    # (legacy path — event_id should always be
                                    # present for FCM-triggered alerts).
                                    continue
                                status = ev.get("videoClipUploadStatus", "")
                                url = ev.get("videoClipUrl", "")
                                if status == "Done" and url:
                                    found_clip_url = url
                                elif status == "Unavailable":
                                    clip_unavailable = True
                                    _LOGGER.debug(
                                        "Alert: clip Unavailable after %ds — stop polling for %s",
                                        (attempt + 1) * 10,
                                        cam_name,
                                    )
                                break
                    if found_clip_url:
                        _LOGGER.debug(
                            "Alert: clip ready after %ds for %s",
                            (attempt + 1) * 10,
                            cam_name,
                        )
                        break
                    if clip_unavailable:
                        break
                except Exception:  # noqa: S112 # resilient poll loop, transient network error on one attempt should not abort all retries
                    continue

        if found_clip_url and _is_safe_bosch_url(found_clip_url):
            try:
                dl_headers = {
                    "Authorization": f"Bearer {coordinator.token}",
                    "Accept": "*/*",
                }
                async with asyncio.timeout(60):
                    async with session.get(found_clip_url, headers=dl_headers) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if data and len(data) > 1000:
                                await coordinator.hass.async_add_executor_job(
                                    _write_file, clip_path, data
                                )
                                size_kb = len(data) // 1024
                                vcaption = f"\U0001f3ac {cam_name} Video ({ts_short}, {size_kb} KB)"
                                await _notify_type(
                                    "video",
                                    vcaption,
                                    clip_path,
                                )
                                _LOGGER.info(
                                    "Alert step 3 (video) sent: %s (%d KB)",
                                    clip_path,
                                    size_kb,
                                )
                                if not save_snapshots:
                                    files_to_cleanup.append(clip_path)
            except Exception as err:
                _LOGGER.warning("Alert step 3 (video) failed: %s", err)
        else:
            _LOGGER.debug("Alert: video clip not ready after 90s for %s", cam_name)

    # -- Mark event as read ------------------------------------------------
    if _clip_cam_id and coordinator.options.get("mark_events_read", False):
        event_id = event_id or coordinator._last_event_ids.get(_clip_cam_id, "")
        if event_id:
            try:
                await async_mark_events_read(coordinator, [event_id])
            except Exception:  # noqa: S110 # best-effort cloud housekeeping; alert delivery already complete
                pass

    # -- SMB upload (immediate, alongside alert) ---------------------------
    if opts.get("enable_smb_upload") and opts.get("smb_server") and _clip_cam_id:
        try:
            # Build a minimal data dict for sync_smb_upload with just this event
            ev_id = event_id or coordinator._last_event_ids.get(_clip_cam_id, "unknown")
            ev_data = {
                "timestamp": timestamp,
                "eventType": event_type,
                "id": ev_id,
                "imageUrl": image_url,
                "videoClipUrl": found_clip_url if found_clip_url else "",
                "videoClipUploadStatus": "Done" if found_clip_url else "",
            }
            smb_data = {
                _clip_cam_id: {
                    "info": {"title": cam_name},
                    "events": [ev_data],
                }
            }
            # Pass pre-downloaded snapshot bytes so sync_smb_upload skips the
            # cloud re-download.  When the camera is streaming, re-downloading
            # via urllib in the executor would compete on the camera's single TLS
            # control channel → RTSP keepalive delay → stream freeze.  When
            # _prefetched_snapshot is None (step 2 skipped / image unavailable),
            # sync_smb_upload falls back to downloading via imageUrl as before.
            _smb_prefetch = _prefetched_snapshot
            _LOGGER.info(
                "Alert: SMB upload starting for %s (event=%s, img=%s, clip=%s, prefetch=%s)",
                cam_name,
                ev_id[:8] if ev_id else "?",
                bool(image_url),
                bool(found_clip_url),
                bool(_smb_prefetch),
            )
            # NOTE: sync_smb_upload runs in an executor thread, and asyncio
            # can only abandon the *await* on a timeout — it cannot kill the
            # underlying OS thread, which would otherwise keep running the
            # upload indefinitely on a hung NAS (thread leak, and a delayed
            # write could still land after a retry has already re-sent the
            # same event). The real cutoff now happens inside sync_smb_upload
            # itself via socket.setdefaulttimeout(_SMB_TRANSFER_TIMEOUT), which
            # bounds every blocking smbclient/smbprotocol call in the transfer
            # loop. This outer wait_for(timeout=30.0) is only a safety margin
            # in case that inner bound is ever bypassed (e.g. a future
            # smbclient version issuing calls outside the socket module) — it
            # is deliberately longer than _SMB_TRANSFER_TIMEOUT so the inner
            # timeout fires first under normal conditions.
            await asyncio.wait_for(
                coordinator.hass.async_add_executor_job(
                    sync_smb_upload,
                    coordinator,
                    smb_data,
                    coordinator.token,
                    _smb_prefetch,
                ),
                timeout=30.0,
            )
            _LOGGER.info("Alert: SMB upload completed for %s", cam_name)
        except TimeoutError:
            _LOGGER.warning("Alert: SMB upload timed out after 30s for %s", cam_name)
        except Exception as err:
            _LOGGER.warning("Alert: SMB upload failed for %s: %s", cam_name, err)

    # -- Local save (FCM-triggered, alongside SMB) -------------------------
    if opts.get("enable_local_save") and opts.get("download_path") and _clip_cam_id:
        try:
            ev_id = event_id or coordinator._last_event_ids.get(_clip_cam_id, "unknown")
            ev_data = {
                "timestamp": timestamp,
                "eventType": event_type,
                "id": ev_id,
                "imageUrl": image_url,
                "videoClipUrl": found_clip_url if found_clip_url else "",
                "videoClipUploadStatus": "Done" if found_clip_url else "",
            }
            await asyncio.wait_for(
                coordinator.hass.async_add_executor_job(
                    sync_local_save, coordinator, ev_data, coordinator.token, cam_name
                ),
                timeout=30.0,
            )
        except TimeoutError:
            _LOGGER.warning("Alert: local save timed out after 30s for %s", cam_name)
        except Exception as err:
            _LOGGER.warning("Alert: local save failed for %s: %s", cam_name, err)

    # -- Cleanup local files -----------------------------------------------
    if delete_after and files_to_cleanup:
        await asyncio.sleep(5)  # give Signal time to read the files
        for fpath in files_to_cleanup:
            try:
                await coordinator.hass.async_add_executor_job(os.remove, fpath)
            except OSError:
                pass


# ── Mark events as read ──────────────────────────────────────────────────────


async def async_mark_events_read(coordinator: Any, event_ids: list[str]) -> bool:
    """Mark events as read/seen on the Bosch cloud via PUT /v11/events.

    The /v11/events/bulk endpoint only supports `{ids, action: "DELETE"}` —
    there is no bulk mark-as-read. Best-effort — never raises.
    """
    if not event_ids:
        return True

    token = coordinator.token
    if not token:
        return False

    session = await async_get_bosch_cloud_session(coordinator.hass)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    success = False
    for eid in event_ids:
        try:
            async with asyncio.timeout(5):
                async with session.put(
                    f"{CLOUD_API}/v11/events",
                    headers=headers,
                    json={"id": eid, "isRead": True},
                ) as resp:
                    if resp.status in (200, 201, 204):
                        success = True
        except Exception:  # noqa: S110 # best-effort mark-read; caller logs success/failure via return value
            pass

    if success:
        _LOGGER.debug("Marked %d events as read", len(event_ids))
    return success


class FCMCoordinatorMixin:
    """Thin coordinator-facing methods delegating to this module's functions.

    Mixed into BoschCameraCoordinator (see __init__.py's class declaration)
    so `coordinator.async_start_fcm_push()` etc. keep working as methods —
    every one of them just forwards `self` to the corresponding free
    function above, which is where the actual FCM logic lives.
    """

    hass: HomeAssistant

    async def _fetch_firebase_config(self) -> dict[str, str]:
        """Fetch Firebase config (delegated to fetch_firebase_config)."""
        return await fetch_firebase_config(self.hass)

    async def async_start_fcm_push(self) -> None:
        """Start the FCM supervisor (delegated to async_ensure_fcm_supervisor)."""
        return await async_ensure_fcm_supervisor(self)

    async def _register_fcm_with_bosch(self) -> bool:
        """Register FCM token with Bosch CBS (delegated to register_fcm_with_bosch)."""
        return await register_fcm_with_bosch(self)

    async def async_stop_fcm_push(self) -> None:
        """Stop the FCM supervisor and push listener (delegated to async_stop_fcm_supervisor)."""
        return await async_stop_fcm_supervisor(self)

    async def _async_handle_fcm_push(self) -> None:
        """Handle an FCM push (delegated to async_handle_fcm_push)."""
        return await async_handle_fcm_push(self)

    def _get_alert_services(self, type_key: str) -> list[str]:
        """Return notify services for a given alert type (delegated to get_alert_services)."""
        return get_alert_services(self, type_key)

    @staticmethod
    def _build_notify_data(
        svc: str,
        message: str,
        file_path: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Build notify service call data (delegated to build_notify_data)."""
        return build_notify_data(svc, message, file_path, title)

    async def _async_send_alert(
        self,
        cam_name: str,
        event_type: str,
        timestamp: str,
        image_url: str,
        clip_url: str = "",
        clip_status: str = "",
        event_id: str = "",
    ) -> None:
        """Send a 3-step alert (delegated to async_send_alert)."""
        return await async_send_alert(
            self,
            cam_name,
            event_type,
            timestamp,
            image_url,
            clip_url,
            clip_status,
            event_id=event_id,
        )

    async def async_mark_events_read(self, event_ids: list[str]) -> bool:
        """Mark events as read on the Bosch cloud (delegated to async_mark_events_read)."""
        return await async_mark_events_read(self, event_ids)

    @staticmethod
    def _write_file(path: str, data: bytes) -> None:
        """Write binary data to file (delegated to the module-level _write_file)."""
        _write_file(path, data)
