"""BoschCameraCoordinator — the shared DataUpdateCoordinator subclass.

Extracted from `__init__.py` (pure structural move, zero behavior change) to
match Core/reolink convention: `__init__.py` handles only config-entry
setup/unload/migrate/platform-forwarding/service-registration, while the
coordinator class itself lives in its own module.

TRUE MINIMAL v1 (snapshot-only): this integration ships the camera platform
only — cloud/LAN snapshot fetch, camera list/status polling, event polling +
dispatch, the RCP read-only probe (via cloud proxy + LAN), and token/auth
handling. There is no live streaming, no FCM push, no Mini-NVR/SMB/Frigate
recording, and no proxy / registration / WebRTC wiring of any kind — every
free-function sibling module that used to back those features has been
removed. The coordinator still delegates to the sibling modules that
remain: camera_list, camera_status, event_polling, event_dispatch,
slow_tier, tick_bootstrap, tick_housekeeping, tick_failure, rcp, token_auth.
"""

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
import ipaddress
import json as _json
import logging
import math
import re as _re
import threading
import time
from typing import Any, override
from urllib.parse import urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import async_digest_request, async_get_bosch_cloud_session, ir
from .camera_list import fetch_camera_list
from .camera_status import poll_statuses
from .cloud_ssl import async_bosch_cloud_session_cm, async_get_bosch_cloud_ssl_context
from .const import (
    CLOUD_API,
    DEFAULT_OPTIONS,
    DOMAIN,
    JPEG_SIZE_FULL,
    RCP_099E_PROBE_FAILURE_MEMO_SEC,
    TIMEOUT_PUT_CONNECTION,
    TIMEOUT_RCP_099E_PROBE,
    TIMEOUT_SNAP,
)
from .event_dispatch import build_data_and_dispatch
from .event_polling import poll_events
from .lock_utils import get_or_create_lock
from .models import get_model_config
from .rcp import async_update_rcp_data
from .slow_tier import (
    _compute_cam_context,
    _poll_cam_control,
    _poll_cam_info_caches,
    _poll_slow_tier_endpoints,
)
from .tick_bootstrap import ensure_feature_flags, ensure_protocol_checked
from .tick_failure import (
    dispatch_client_error,
    dispatch_timeout,
    dispatch_update_failed,
)
from .tick_housekeeping import run_housekeeping
from .token_auth import TokenAuthCoordinatorMixin

_LOGGER = logging.getLogger(__name__)

# Coalesce concurrent async_fetch_fresh_event_snapshot calls for the same camera.
# After an FCM push all HA consumers wake simultaneously and each requests the latest
# event thumbnail. 8 s covers the burst window; the 60 s scan cycle always gets fresh data.
_FRESH_SNAP_TTL = 8.0

# Event-poll cadence while FCM push is NOT delivering (disabled, or watchdog
# flagged unhealthy). The relaxed `interval_events` (default 300 s) assumes
# push carries the near-instant detection and the poll is only a safety net —
# but with push dead the poll IS the detection path, and a 300 s poll behind a
# 90 s motion window means a polled event is already older than the window the
# moment it lands, so the binary sensor can never turn ON (issue #36). When
# push is not delivering we therefore poll at this fast cadence instead — bounded
# below the smallest motion window (MOTION_ACTIVE_WINDOW_MIN/DEFAULT) so a
# polled event is always seen while still "fresh". A user who explicitly set a
# lower `interval_events` keeps it (min() below).
FCM_DOWN_EVENT_POLL_SEC = 60.0

# Grace before a camera's online→offline transition is ANNOUNCED (push/notify).
# Cameras on a Wi-Fi repeater/mesh briefly drop during a repeater restart or a
# DFS channel change and recover within a minute or two; firing an "offline /
# live + snapshots unavailable" notification on the first failed status check is
# noise. Only announce offline once the camera has stayed offline continuously
# for this long. A recovery within the window produces no notification at all.
# The camera ENTITY availability still flips immediately — only the notification
# is debounced.
CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC = 300.0  # 5 min

# ── URL allowlist for image/video downloads (SSRF prevention) ────────────────
_SAFE_DOMAINS = frozenset({".boschsecurity.com", ".bosch.com"})


def _is_safe_bosch_url(url: str) -> bool:
    """Validate that a URL points to a known Bosch domain (HTTPS only).

    ``urlparse`` can raise ``ValueError`` on malformed input (unmatched IPv6
    brackets, invalid NFKC-normalized netloc) — fail closed rather than let
    it propagate to callers that don't expect it (same class of gap fixed
    in ``_is_safe_bosch_host``, Copilot review round 18).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and any(parsed.hostname.endswith(d) for d in _SAFE_DOMAINS)
    )


def _is_safe_bosch_host(host_and_port: str) -> bool:
    """Validate a bare ``host[:port]`` string (no scheme) against the Bosch allowlist.

    Used for the RCP proxy host/hash pair Bosch's cloud PUT /connection
    response hands back (e.g. "proxy-01.live.cbs.boschsecurity.com:42090")
    before it is used to build a request URL for the RCP client library —
    an unvalidated value here is an SSRF path (bug-hunt 2026-07-27, Copilot
    review round 5). Parsed via ``urlparse`` (not a naive ``rsplit(":", 1)``)
    so this extracts the same authority a real HTTP client would connect to
    — a value like "proxy.boschsecurity.com:443@attacker.example" splits to
    an allowlisted-looking "proxy.boschsecurity.com" on the last colon, but
    an HTTP client parses it as userinfo and connects to attacker.example
    (Copilot review round 18). A legitimate Bosch value never contains "@",
    so it's rejected outright rather than relying on userinfo-vs-host
    semantics alone — aiohttp turns userinfo into a Basic-Auth header, which
    would otherwise reach Bosch's real proxy with attacker-controlled
    credentials. ``urlparse`` itself can raise ``ValueError`` on malformed
    input (unmatched IPv6 brackets, invalid NFKC-normalized netloc) — fail
    closed rather than let it propagate past the caller's narrower
    ``except (TimeoutError, aiohttp.ClientError)``.
    """
    if "@" in host_and_port:
        return False
    try:
        hostname = urlparse(f"https://{host_and_port}").hostname
    except ValueError:
        return False
    return hostname is not None and any(hostname.endswith(d) for d in _SAFE_DOMAINS)


def _parse_safe_rcp_proxy_url(url_entry: str, cam_id: str) -> tuple[str, str] | None:
    """Split a Bosch ``urls[0]`` proxy entry into ``(host, hash)``, validated.

    Returns None (logging a warning) for a malformed entry or one whose host
    fails `_is_safe_bosch_host` — never hands back an unvalidated host to a
    caller that will use it to build a request URL.
    """
    parts = url_entry.split("/", 1)
    if len(parts) != 2 or not _is_safe_bosch_host(parts[0]):
        _LOGGER.warning(
            "Rejected unsafe/malformed RCP proxy entry for %s: %s",
            cam_id,
            url_entry[:60],
        )
        return None
    return parts[0], parts[1]


def _is_safe_local_camera_host(host_and_port: str) -> bool:
    """Validate a Bosch-issued LOCAL camera ``host:port`` before use.

    Unlike the RCP proxy host (validated against a Bosch-domain allowlist,
    since that value legitimately points at Bosch's own cloud
    infrastructure), a LOCAL session's host is expected to be the physical
    camera's own private LAN address. Accepting an arbitrary/public host
    here would let a compromised or malicious PUT /connection response
    redirect the snapshot request — made with TLS verification disabled —
    to an arbitrary host, and that same host is cached for later outage
    fallback, extending the exposure window (Copilot review round 7).
    Link-local addresses are explicitly excluded even though Python's
    `is_private` counts them as private — 169.254.169.254 is the
    well-known cloud-metadata SSRF target, and a physical camera's LOCAL
    address is never link-local in practice.
    """
    host, _, port_str = host_and_port.partition(":")
    if not port_str.isdigit() or not 1 <= int(port_str) <= 65535:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_private and not addr.is_link_local


# These four keys are fixed per Bronze's appropriate-polling rule — their
# options-flow UI fields were removed, but a HACS-migrated config entry can
# still carry a user's old custom value under the same key names in
# `entry.options`, which a plain dict merge would silently keep honoring
# (bug-hunt 2026-07-27, Copilot review round 3).
_FIXED_POLLING_OPTION_KEYS = (
    "scan_interval",
    "interval_status",
    "interval_events",
    "snapshot_interval",
)


def get_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return entry options merged with defaults.

    The fixed-polling keys are always taken from DEFAULT_OPTIONS, never from
    `entry.options` — see `_FIXED_POLLING_OPTION_KEYS`.
    """
    opts: dict[str, Any] = dict(DEFAULT_OPTIONS)
    opts.update(
        {k: v for k, v in entry.options.items() if k not in _FIXED_POLLING_OPTION_KEYS}
    )
    return opts


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraCoordinator(
    DataUpdateCoordinator,
    TokenAuthCoordinatorMixin,
):
    """Shared coordinator — fetches all camera data once per scan_interval.

    All entity types (camera, sensor, button) read from coordinator.data
    rather than making independent API calls.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator for a config entry."""
        self.entry = entry
        # Advanced diagnostic escape hatch (set via the manual-login/relogin
        # "Advanced" field) — NEVER defaulted to any specific host. Only ever
        # non-empty if a user explicitly typed a Bosch-confirmed alternate
        # camera-API base URL in to test whether their account is registered
        # there instead of production (2026-07-06 SebastianHarder
        # investigation). Deliberately narrow-scope (CAUTION: never expand
        # this to redirect real camera-cloud traffic — the point is to probe
        # ONE endpoint, not to run the integration against non-production
        # Bosch infrastructure): only `camera_list.fetch_camera_list` reads
        # `self._cloud_api` — every other request (status/events/snapshots/
        # RCP/writes) always uses the module-level `CLOUD_API`, on purpose
        # (Copilot review round 14 — the field name/log below now say so
        # explicitly, since neither previously stated the scope).
        cloud_api_override = entry.data.get("cloud_api_override", "")
        # Validated against the same Bosch-domain allowlist as image/video
        # URLs — this field has no UI in this (Core) config flow at all and
        # can only ever be present as legacy data inherited from a
        # HACS-migrated entry, so it must never be trusted blindly: every
        # request built from `self._cloud_api` attaches the real bearer
        # token, and an unvalidated override could exfiltrate it to an
        # arbitrary host (Copilot review round 11).
        if cloud_api_override and not _is_safe_bosch_url(cloud_api_override):
            _LOGGER.warning(
                "Ignoring cloud_api_override %s — not a recognized Bosch "
                "domain, falling back to the default camera API",
                cloud_api_override,
            )
            cloud_api_override = ""
        self._cloud_api = cloud_api_override or CLOUD_API
        if cloud_api_override:
            _LOGGER.warning(
                "Using diagnostic camera-API override %s for the initial "
                "camera-list probe only (not for status/events/snapshots/"
                "writes, which always use the production API) — this "
                "should only be set for troubleshooting a specific account "
                "issue with Bosch support's guidance",
                cloud_api_override,
            )
        opts = get_options(entry)
        # Snapshot of options at coordinator creation — used by _async_options_updated
        # to distinguish real options edits from data-only updates (e.g. token refresh).
        # Must be a deep-ish copy so later entry.options mutations don't silently update it.
        self._options_snapshot: dict[str, Any] = dict(opts)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(opts.get("scan_interval", 60))),
        )
        # Local-RCP+ state cache: per-cam {"privacy_mode": bool, "led_dimmer": int, "fetched_at": float, "source": "local"|"remote"}
        # Refreshed opportunistically after a successful RCP fetch. Used as a
        # refinement source for SHC-cache values when SHC is offline / not
        # configured.
        self._rcp_state_cache: dict[str, dict[str, Any]] = {}
        # Per-camera audio setting — True = audio+video on (default), False = snapshot-only
        self.audio_enabled: dict[str, bool] = {}
        # Per-camera card playback volume 0-100 — the automatable, cross-session
        # source of truth the Lovelace card applies to its <video> (browser has
        # no backend volume knob; this is a virtual preference). Mirrors the
        # audio_enabled pattern: in-memory, seeded to a default per camera.
        self.audio_volume: dict[str, int] = {}
        # Camera entity references — registered on entity setup, used by button/service
        self.camera_entities: dict[str, Any] = {}
        # Image entity references — registered on image platform setup
        # Keyed by cam_id; image entities call async_notify_refreshed() after
        # each disk-persist so WKWebView gets a fresh signed URL.
        self.image_entities: dict[str, Any] = {}
        # Per-type last-fetched timestamps (-inf = never → always fetch on first tick)
        self._first_tick_done: bool = False
        self._last_status: float = -math.inf  # force status check on first tick
        self._last_events: float = -math.inf  # force event check on first tick
        self._last_slow: float = -math.inf  # force slow check on first tick
        # Per-camera set of cam_ids whose slow-tier diagnostic fetch was
        # deferred this tick. SENTINEL_RULE: set membership is the flag, not
        # a 0.0/float('inf') timestamp.
        self.slow_tier_deferred: set[str] = set()
        # Per-cam monotonic timestamp of when the *current* unbroken deferral
        # started, so a continuously-active stream cannot starve diagnostics
        # forever: once now - start >= SLOW_TIER_MAX_DEFER_SEC we force one read
        # despite the stream. Entry cleared whenever the deferred fetch runs.
        self.slow_tier_defer_since: dict[str, float] = {}
        # Cached data for types that are not re-fetched this tick
        self.cached_status: dict[str, str] = {}
        # Per-cam time (monotonic) the cloud last returned HTTP 444 (session
        # quota / not-ready, e.g. a freshly re-paired camera). For a short window
        # after, WRITE paths skip the cloud and go straight to the LAN/SHC
        # fallback instead of re-hitting the cloud for another 444. -inf = never.
        self.cloud_444_at: dict[str, float] = {}
        self.cached_events: dict[str, list[Any]] = {}
        # Cloud-derived state cache — keyed by cam_id. Each entry:
        # {"device_id": str, "camera_light": bool|None, "privacy_mode": bool|None, ...}
        # Populated directly from `/v11/video_inputs` fields by
        # slow_tier._poll_cam_info_caches (no local SHC API involved).
        self.shc_state_cache: dict[str, dict[str, Any]] = {}
        # Pan position cache — keyed by cam_id, only populated for cameras with panLimit > 0
        self.pan_cache: dict[str, int | None] = {}
        # WiFi info cache — keyed by cam_id, populated from GET /wifiinfo
        self.wifiinfo_cache: dict[str, dict[str, Any]] = {}
        # Ambient light sensor cache — keyed by cam_id, populated from GET /ambient_light_sensor_level
        self.ambient_light_cache: dict[str, float | None] = {}
        # RCP data caches — keyed by cam_id, populated via RCP protocol over cloud proxy
        self.rcp_dimmer_cache: dict[str, int | None] = {}  # LED dimmer value 0-100
        self.rcp_privacy_cache: dict[
            str, int | None
        ] = {}  # privacy mask byte[1] (1=ON)
        self.rcp_clock_offset_cache: dict[
            str, float | None
        ] = {}  # camera clock offset vs server (seconds)
        self.rcp_lan_ip_cache: dict[
            str, str | None
        ] = {}  # camera LAN IP via RCP 0x0a36
        self.rcp_product_name_cache: dict[
            str, str | None
        ] = {}  # camera product name via RCP 0x0aea
        self.rcp_bitrate_cache: dict[
            str, list[int]
        ] = {}  # bitrate ladder kbps from 0x0c81
        # Phase 2 RCP caches
        self.rcp_alarm_catalog_cache: dict[
            str, list[dict[str, Any]]
        ] = {}  # alarm types from 0x0c38
        self.rcp_motion_zones_cache: dict[
            str, list[dict[str, Any]]
        ] = {}  # motion zones from 0x0c00
        self.rcp_motion_coords_cache: dict[
            str, list[dict[str, Any]]
        ] = {}  # zone coords from 0x0c0a
        self.rcp_tls_cert_cache: dict[
            str, dict[str, Any]
        ] = {}  # TLS cert info from 0x0b91
        self.rcp_network_services_cache: dict[
            str, list[str]
        ] = {}  # network services from 0x0c62
        self.rcp_iva_catalog_cache: dict[
            str, list[dict[str, Any]]
        ] = {}  # IVA analytics from 0x0b60
        # Commands that consistently return error=0x90 (not supported via proxy).
        # Key: cam_id, value: set of command hex strings. After 3 consecutive
        # failures the command is skipped for the rest of the session.
        self._rcp_cmd_failures: dict[
            str, dict[str, int]
        ] = {}  # cam_id → {cmd → fail_count}
        # Video quality preference — keyed by cam_id, runtime only (not persisted)
        # Values: "auto" | "high" | "low". Still used by get_quality_params()
        # to pick highQualityVideo/inst for the REMOTE proxy connection opened
        # for RCP diagnostic reads and live-snapshot fetches (no streaming
        # entity survives in this minimal build, but the preference knob and
        # its effect on connection params are shared with those call sites).
        self._quality_preference: dict[str, str] = {}
        # RCP session ID cache — keyed by proxy_hash, value (session_id, expires_monotonic)
        # Avoids 2 round-trip RCP handshake on every thumbnail/data fetch
        self.rcp_session_cache: dict[str, tuple[str, float]] = {}
        # Per-proxy_hash lock serializing RCP session opens. Bosch's cloud RCP
        # proxy only tolerates one live session per proxy_hash — two concurrent
        # openers (e.g. a privacy-mode toggle's snapshot trigger racing the
        # coordinator's RCP data refresh) each fire their own 0xff0c/0xff0d
        # handshake, and the proxy rejects whichever loses the race with
        # sessionid 0x00000000 ("proxy rejected"), seen live 2026-07-08.
        # Serializing on this lock makes the second caller await the first's
        # in-flight open and then read the now-populated cache instead.
        self.rcp_session_locks: dict[str, asyncio.Lock] = {}
        # Proxy URL cache — keyed by cam_id, value (urls[0], expires_monotonic)
        # Proxy leases last ~60s; cache for 50s to skip PUT /connection on warm refreshes
        self._proxy_url_cache: dict[str, tuple[str, float]] = {}
        # GitHub #56: cam_id → monotonic timestamp until which the RCP 0x099e
        # thumbnail probe is skipped, after it timed out/failed/errored. A
        # camera that can never satisfy 0x099e (observed on some Gen1 units)
        # would otherwise pay the probe's full 2-8s cost on every single
        # snapshot fetch, forever, starving the snap.jpg leg's timeout budget.
        # Re-probed hourly so a firmware update can re-enable the fast path;
        # cleared immediately on any success.
        self._rcp_099e_probe_failed_until: dict[str, float] = {}
        # Per-camera lock serializing async_fetch_live_snapshot calls.
        # Prevents duplicate PUT /connection when first-load + proactive refresh
        # overlap, or when a user rapid-triggers snapshots.
        self._snapshot_fetch_locks: dict[str, asyncio.Lock] = {}
        # Short-lived cache for async_fetch_fresh_event_snapshot.
        # After a push/poll-detected event, async_update_listeners() wakes
        # all HA consumers simultaneously; each calls async_image() →
        # async_fetch_fresh_event_snapshot. Without coalescing this fires
        # 8+ identical cloud round-trips in ~200 ms. The lock (created
        # lazily per cam_id) serialises concurrent callers: the first one
        # fetches and stores the result; the rest acquire the lock after it
        # releases, find the cache hit, and return without a network call.
        # TTL=8s covers the burst window while staying well inside the 60s scan cycle.
        self._fresh_snap_cache: dict[str, tuple[bytes, float]] = {}
        self._fresh_snap_locks: dict[str, asyncio.Lock] = {}
        # Last-seen event IDs per camera — used to detect new events for snapshot refresh
        self.last_event_ids: dict[str, str] = {}
        # Epoch timestamp of coordinator start — used to reject event downloads for
        # events that predate this session (e.g. queued FCM pushes arriving after reload).
        self._download_started_at: float = time.time()
        # Alert-sent cache keyed by event_id → monotonic timestamp. Bosch can
        # send two FCM pushes ~10 s apart for the same MOVEMENT event (once at
        # detection start, again when the clip is finalized), and concurrent
        # push handlers race on `last_event_ids` before either commits. This
        # cache blocks the second alert dispatch when the ID was already
        # alerted within 60 s. Pruned to the 32 most recent entries to bound
        # memory.
        self.alert_sent_ids: dict[str, float] = {}
        # FCM push is not part of this minimal build (fcm.py removed) — these
        # flags stay at their "push not running" defaults forever, so
        # event_dispatch.py's push-vs-poll delivery-death check (a KEPT
        # module) always takes the poll-only path. Kept as real attributes
        # (not removed) because event_dispatch.py reads them directly.
        self.fcm_running: bool = False
        self.fcm_last_push: float = -math.inf
        self.fcm_started_at: float = -math.inf
        self.fcm_healthy: bool = False
        self.fcm_force_hard_heal: bool = False
        # Lock serializing cross-thread FCM state writes — no longer written
        # from a Firebase thread in this build, but event_dispatch.py still
        # takes it around its fcm_healthy read for defensive consistency.
        self.fcm_lock: threading.Lock = threading.Lock()
        # Unread events count cache — keyed by cam_id, populated from GET /unread_events_count
        self.unread_events_cache: dict[str, int] = {}
        # Privacy sound override cache — keyed by cam_id, populated from GET /privacy_sound_override
        self.privacy_sound_cache: dict[str, bool | None] = {}
        # Commissioned status cache — keyed by cam_id, populated from GET /commissioned
        self.commissioned_cache: dict[str, dict[str, Any]] = {}
        # Feature flags — populated once from GET /v11/feature_flags
        self.feature_flags: dict[str, bool] = {}
        # Protocol version check — run once at startup
        self.protocol_checked: bool = False
        # Firmware update status cache — keyed by cam_id, from GET /firmware
        self.firmware_cache: dict[str, dict[str, Any]] = {}
        # SMB/NVR upload+recording are not part of this minimal build (smb.py
        # and recorder.py removed) — these timestamps are kept only because
        # tick_housekeeping.py (a KEPT module) still reads/writes them; the
        # `enable_smb_upload`/`enable_nvr` options default False so the
        # background-cleanup branches that would call the (now removed)
        # coordinator methods never actually fire.
        self.last_smb_cleanup: float = -math.inf
        self.last_nvr_cleanup: float = -math.inf
        # Token refresh failure tracking — alert once, not every 80s
        self._token_alert_sent: bool = False  # True after first alert sent
        self._token_fail_count: int = 0  # consecutive refresh failures
        # Consecutive refresh-timeout failures — tracked separately from
        # _token_fail_count. A timeout proves nothing about the refresh
        # token's validity (Keycloak/network unresponsive, not invalid_grant),
        # so it must never contribute toward the reauth-escalation count —
        # only a genuine invalid-grant response or a completed-but-empty
        # token response does that (bug-hunt 2026-07-27, Copilot review
        # round 4).
        self._token_timeout_fail_count: int = 0
        # Bosch auth-server outage tracking — distinct from hard failures.
        # 5xx from Keycloak = Bosch infrastructure problem, NOT user/config issue:
        # no reauth trigger, no escalation, just back off and retry.
        self.auth_outage_count: int = 0  # consecutive 5xx responses
        self._auth_outage_next_retry_ts: float = -math.inf  # monotonic time gate
        # Cached LOCAL Digest credentials per camera — survives live-connection
        # teardown. Populated on every successful PUT /connection LOCAL and used
        # as a fallback path (snap.jpg, Gen2 RCP privacy writes) when the Bosch
        # cloud is unreachable. Creds are ephemeral (camera rotates them on
        # reboot) but usually stable for minutes to hours.
        # {cam_id: {"user": str, "password": str, "host": str, "port": int, "ts": monotonic}}
        self.local_creds_cache: dict[str, dict[str, Any]] = {}
        # Persistent stores for cross-restart caches — set once in
        # async_setup_entry (__init__.py), read/written from there and from
        # tick_housekeeping.py.
        self.cloud_alert_store: Store | None = None
        self.lan_ips_store: Store | None = None
        self.hw_version_store: Store | None = None
        self.local_creds_store: Store | None = None
        # Last-written snapshot of each store above, for change-detection —
        # tick_housekeeping.py only writes when the current value differs
        # from these, to avoid redundant disk I/O every tick.
        self.lan_ips_snapshot: dict[str, str] | None = None
        self.hw_version_snapshot: dict[str, str] | None = None
        self.local_creds_snapshot: dict[str, dict[str, Any]] | None = None
        # Serializes ensure_valid_token so concurrent refreshes don't race
        # (Keycloak rotates refresh_token and invalidates the previous one —
        # two parallel POSTs with the same token → first wins, second gets
        # invalid_grant and permanently breaks the loop).
        self._token_refresh_lock: asyncio.Lock = asyncio.Lock()
        # TimerHandle for the next scheduled proactive token refresh.
        # Held so async_unload_entry can cancel it — otherwise a config
        # reload leaks timers that still fire against a dead coordinator.
        self.token_refresh_handle: asyncio.TimerHandle | None = None
        # Strong references to fire-and-forget background tasks so the GC
        # does not cancel them mid-flight. Self-removing via done_callback.
        self.bg_tasks: set[asyncio.Task[Any]] = set()
        # Timestamp overlay cache — keyed by cam_id, from GET /timestamp
        self.timestamp_cache: dict[str, bool | None] = {}
        # Status LED cache — keyed by cam_id, from GET /ledlights (Gen2 only)
        self.ledlights_cache: dict[str, bool | None] = {}
        # Lens elevation cache — keyed by cam_id, from GET /lens_elevation (Gen2 only)
        self.lens_elevation_cache: dict[str, float | None] = {}
        # Audio settings cache — keyed by cam_id, from GET /audio (Gen2 only)
        self.audio_cache: dict[str, dict[str, Any]] = {}
        # Motion light cache — keyed by cam_id, from GET /lighting/motion (Gen2 only)
        self.motion_light_cache: dict[str, dict[str, Any]] = {}
        # Image rotation 180° flag — keyed by cam_id, indoor cameras only.
        # No API call — purely a client-side display flag for ceiling-mounted cams.
        # Read by camera.async_camera_image (rotates JPEG via PIL) and by the
        # Pan number entity (inverts sign so "right" stays "right" on screen).
        # State is owned by BoschImageRotation180Switch (RestoreEntity).
        self.image_rotation_180: dict[str, bool] = {}
        # External stream URL exposure flag — keyed by cam_id, default False.
        # Owned by BoschExternalStreamSwitch (RestoreEntity). When True, the
        # per-camera BoschStreamUrlSensor + BoschStreamUrlSubSensor expose the
        # current LOCAL/REMOTE rtspsUrl (inst=1) and a derived inst=2 sub-stream
        # URL so users can paste them into Frigate / BlueIris configs.
        # Default OFF — opt-in per camera, avoids entity-spam.
        self.external_stream_enabled: dict[str, bool] = {}
        # Ambient lighting config cache — keyed by cam_id, from GET /lighting/ambient (Gen2 only)
        self.ambient_lighting_cache: dict[str, dict[str, Any]] = {}
        # Lighting switch cache — keyed by cam_id, from GET /lighting/switch (Gen2 only)
        self.lighting_switch_cache: dict[str, dict[str, Any]] = {}
        # Global lighting config cache — keyed by cam_id, from GET /lighting (Gen2 only)
        # Contains: darknessThreshold (0.0-1.0), softLightFading (bool)
        self.global_lighting_cache: dict[str, dict[str, Any]] = {}
        # Notification type toggles cache — keyed by cam_id, from GET /notifications
        self.notifications_cache: dict[str, dict[str, Any]] = {}
        # Rules cache — keyed by cam_id, from GET /rules
        self.rules_cache: dict[str, list[Any]] = {}
        # Cloud motion zones cache — keyed by cam_id, from GET /motion_sensitive_areas
        self.cloud_zones_cache: dict[str, list[Any]] = {}
        # Cloud privacy masks cache — keyed by cam_id, from GET /privacy_masks
        self.cloud_privacy_masks_cache: dict[str, list[Any]] = {}
        # Lighting options cache — keyed by cam_id, from GET /lighting_options
        self.lighting_options_cache: dict[str, dict[str, Any]] = {}
        # Intrusion detection config cache — keyed by cam_id, from GET /intrusionDetectionConfig (Gen2 only)
        self.intrusion_config_cache: dict[str, dict[str, Any]] = {}
        # Audio detection config cache — keyed by cam_id, from GET /audioDetectionConfig
        # (Gen2 Audio-Plus). Contains: detectGlassBreak, detectFireAlarm (both bool).
        self.audio_detection_cache: dict[str, dict[str, Any]] = {}
        # Alarm settings cache — from GET /alarm_settings (Gen2 Indoor II only).
        # Contains: alarmMode, alarmDelayInSeconds, alarmActivationDelaySeconds,
        #          preAlarmMode, preAlarmDelayInSeconds
        self.alarm_settings_cache: dict[str, dict[str, Any]] = {}
        # Alarm status cache — from GET /alarmStatus (Gen2 Indoor II only).
        self.alarm_status_cache: dict[str, dict[str, Any]] = {}
        # Last observed alarmType per cam — for rising-edge detection of intrusion
        # events. Fires `bosch_shc_camera_intrusion` when alarmType transitions
        # from NONE/empty to a real alarm type (e.g. INTRUSION_DETECTED).
        self._last_alarm_type: dict[str, str] = {}
        # Intrusion system arming cache — derived from alarmStatus (armed/disarmed).
        # Set by BoschAlarmSystemArmSwitch on successful PUT /intrusionSystem/arming.
        self.arming_cache: dict[str, bool] = {}
        # Status LED brightness cache (Gen2 Indoor II) — from GET /iconLedBrightness.
        # Value range: 0-4 (0 = off, 4 = max).
        self.icon_led_brightness_cache: dict[str, int] = {}
        # Gen2 polygon zones cache — keyed by cam_id, from GET /zones (Gen2 only)
        # Contains polygon zones with trigger: "PERSON", maskType, color fields
        self.gen2_zones_cache: dict[str, list[Any]] = {}
        # Gen2 private areas cache — keyed by cam_id, from GET /privateAreas (Gen2 only)
        # Contains privacy mask polygons with color: "#000000"
        self.gen2_private_areas_cache: dict[str, list[Any]] = {}
        # userToken cache — keyed by cam_id, from GET /credentials
        self._user_token_cache: dict[str, str] = {}
        # Separate timer for lighting/switch — polled every tick (60s) instead of slow tier (300s)
        # Bosch app polls this every ~40s; slow tier (300s) is too slow for responsive light state
        self._last_lighting_switch: float = -math.inf
        # Write-lock timestamps — prevent coordinator from overwriting optimistic state
        # with stale cloud data in the seconds after a successful API write.
        # Keyed by cam_id, value is monotonic time of last successful write
        # (SENTINEL_RULE: -inf, never 0.0). Read via is_write_locked()/get()
        # by slow_tier.py and the write helpers below.
        self.light_set_at: dict[str, float] = {}  # lighting_override write timestamp
        self.notif_set_at: dict[str, float] = {}  # enable_notifications write timestamp
        # Tracks cam_ids for which a "notifications disabled" WARN has been logged.
        # Cleared when the camera re-enables notifications so the WARN re-fires if
        # they are disabled again later.
        self._notif_disabled_logged: set[str] = set()
        # Tracks cam_ids for which a "firmware update available" INFO has been
        # logged. Cleared once the update installs (upToDate flips back to  # codespell:ignore
        # True) so the INFO re-fires for the next update.
        self._fw_update_alerted: set[str] = set()
        self.privacy_set_at: dict[str, float] = {}  # privacy write timestamp
        self.privacy_sound_set_at: dict[str, float] = {}  # privacy_sound_override write
        self.timestamp_set_at: dict[str, float] = {}  # timestamp overlay write
        self.ledlights_set_at: dict[str, float] = {}  # status LED write
        self.arming_set_at: dict[str, float] = {}  # alarm system arm/disarm write
        self.intrusion_config_set_at: dict[
            str, float
        ] = {}  # intrusionDetectionConfig write
        self.audio_detection_set_at: dict[
            str, float
        ] = {}  # audioDetectionConfig write (glass-break / fire-alarm)
        self.motion_set_at: dict[str, float] = {}  # motion sensitivity write
        self.alarm_settings_set_at: dict[str, float] = {}  # alarm_settings write
        self.lighting_options_set_at: dict[str, float] = {}  # lighting schedule write
        self.WRITE_LOCK_SECS = (
            30.0  # seconds to hold write lock (Bosch cloud propagation can take 20s+)
        )
        # Camera hardware version cache — keyed by cam_id, e.g. "CAMERA_360", "CAMERA_EYES"
        # Used for model-specific timing (encoder warm-up) and feature gating.
        self.hw_version: dict[str, str] = {}
        # TCP reachability cache — (reachable, monotonic_ts). TTL 60s.
        # Populated by async_local_tcp_ping (status loop, camera_status.py).
        self.lan_tcp_reachable: dict[str, tuple[bool, float]] = {}
        # Monotonic timestamp of the last successful local-RCP write per cam.
        # The camera briefly tears down its cloud session when Digest creds
        # rotate after an RCP write; we use this to suppress LAN-offline
        # false positives during that ~30 s window. Default `-math.inf`
        # per SENTINEL_RULE so "never written" never satisfies the grace check.
        self.local_write_at: dict[str, float] = {}
        # During a cloud outage we kick a periodic ping of every known cam IP
        # so dependent entities have a recent reachability signal even though
        # the cloud-driven status loop is blocked. Tracks last outage-ping
        # tick to throttle to once per ~30 s.
        self._last_outage_ping_at: float = -math.inf
        # Offline tracking — per camera, monotonic timestamp when first detected offline.
        # Used to extend status check intervals for persistently offline cameras.
        self.offline_since: dict[str, float] = {}
        # Extended offline interval: cameras offline for >15 min are checked every 15 min
        # instead of the normal interval_status (5 min), reducing unnecessary cloud calls.
        self._OFFLINE_EXTENDED_INTERVAL = 900  # 15 minutes
        # Per-camera status check timestamps (for extended offline intervals)
        self.per_cam_status_at: dict[str, float] = {}
        # Per-camera last observed availability ("online" / "offline" /
        # "unknown"). First observation is silent so a HA restart while a
        # camera is offline does not re-announce. Transitions involving
        # "unknown" are also silent — those are coordinator transient flaps,
        # not real availability changes.
        self._last_camera_status: dict[str, str] = {}
        # Monotonic ts a camera was first observed offline (for the announce
        # grace window — CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC). Cleared as soon as
        # the camera is seen online again, so a brief repeater/Wi-Fi blip never
        # produces an offline notification.
        self._offline_seen_at: dict[str, float] = {}
        # Bosch cloud reachability tracker. Fires user notifications on the
        # transitions (healthy → outage) and (outage → recovered). One-tick
        # blips are suppressed by requiring _CLOUD_OUTAGE_NOTIFY_AFTER_S of
        # continuous failure before announcing the outage. The recovery
        # notification fires immediately when the next tick succeeds.
        self._cloud_outage_started_at: float | None = None
        self.cloud_outage_notified: bool = False
        self._CLOUD_OUTAGE_NOTIFY_AFTER_S: float = 60.0
        # ── Session-quota (HTTP 444) tracker ─────────────────────────────────
        # Timestamps of recent 444 hits per camera (monotonic). Entries older
        # than _SESSION_QUOTA_WINDOW_S are pruned on each new hit. When ≥3
        # hits occur within the window a persistent notification is shown.
        self._session_quota_hits: dict[str, list[float]] = {}
        self._SESSION_QUOTA_WINDOW_S: float = 300.0  # 5 minutes
        self._SESSION_QUOTA_NOTIFY_THRESHOLD: int = 3

    def get_model_config(self, cam_id: str) -> Any:
        """Return CameraModelConfig for a camera (from models.py)."""
        hw = self.hw_version.get(cam_id, "CAMERA")
        return get_model_config(hw)

    @staticmethod
    def err_str(err: BaseException) -> str:
        """Format an exception so empty-message types still produce useful output.

        Covers TimeoutError and some aiohttp errors. Falls back to repr(err)
        when str(err) is empty — the original "fetch error: " empty-tail bug
        shipped for months before this helper.
        """
        s = str(err)
        return s or repr(err)

    def _alert_services(self) -> list[str]:
        """Return configured notify service name(s) for system alerts.

        Covers camera online-offline / cloud-outage alerts. Minimal v1: a
        single `alert_notify_service` option (no FCM-specific
        per-alert-type overrides — fcm.py's routing helpers were removed
        along with FCM push). Empty when unconfigured.
        """
        val = self.options.get("alert_notify_service")
        if not val:
            return []
        return [val] if isinstance(val, str) else list(val)

    def is_write_locked(self, cam_id: str, set_at_dict: dict[str, float]) -> bool:
        """Return True if a fresh user-write is still inside the eventual-consistency window.

        Used by every coordinator slow-tier endpoint handler that polls a
        cloud field also writable from a switch entity. Without this guard,
        a poll within `WRITE_LOCK_SECS` of the user toggle can revert the
        cache to the stale cloud value before it has caught up — the bug
        shape that bit privacy_mode + camera_light in v11.0.x. Keep the
        whole pattern in one helper so future cache fields can opt in with
        a one-liner.
        """
        ts = set_at_dict.get(cam_id)
        return ts is not None and (time.monotonic() - ts) < self.WRITE_LOCK_SECS

    def is_camera_online(self, cam_id: str) -> bool:
        """Return True if this camera's last known status is ONLINE.

        Used by switch/sensor entities to gate availability — prevents commands
        from firing at offline cameras where they cannot be executed.
        Cloud-only switches (Privacy, Notifications) bypass this check since
        those API calls succeed regardless of camera reachability.
        """
        return bool(self.data.get(cam_id, {}).get("status", "UNKNOWN") == "ONLINE")

    def spawn_tracked(
        self, coro: Coroutine[Any, Any, Any], *, name: str
    ) -> asyncio.Task[Any]:
        """Fire-and-forget a coroutine as a tracked task in `bg_tasks`.

        An untracked `hass.async_create_task` is not awaited or cancelled by
        `_async_cancel_coordinator_tasks` on unload/HA-stop — it either gets
        silently orphaned or, on a fast reload, can still be running against
        an already-torn-down coordinator. This is a thin wrapper so every
        one-shot spawn (event_dispatch.py / tick_failure.py /
        tick_housekeeping.py / camera_status.py / this module) goes through
        the same tracked path without duplicating the add/discard
        boilerplate. Not for `while True` loops.
        """
        task = self.hass.async_create_task(coro, name=name)
        self.bg_tasks.add(task)
        task.add_done_callback(self.bg_tasks.discard)
        return task

    # ── Local health check ────────────────────────────────────────────────────
    # Grace period after a local RCP write during which LAN-ping failures are
    # treated as still-reachable: the camera rotates Digest creds + tears down
    # its cloud TLS session after each write, and the LAN HTTPS endpoint is
    # briefly unresponsive (~5-15 s observed). 30 s leaves margin without
    # masking a real network outage.
    LOCAL_WRITE_GRACE_S: float = 30.0

    def _in_local_write_grace(self, cam_id: str, now: float | None = None) -> bool:
        """True if this cam was written to via local RCP within LOCAL_WRITE_GRACE_S."""
        moment = now if now is not None else time.monotonic()
        last = self.local_write_at.get(cam_id, -math.inf)
        return (moment - last) < self.LOCAL_WRITE_GRACE_S

    def is_lan_reachable(self, cam_id: str) -> bool | None:
        """Most recent LAN-TCP reachability for `cam_id`, or None if unknown.

        Honors `local_write_at` grace period — during the post-write window
        we report the last *positive* reachability (or True if none recorded)
        so the UI does not flip to offline for a few seconds after every
        privacy/light toggle.
        """
        entry = self.lan_tcp_reachable.get(cam_id)
        if entry is None:
            return True if self._in_local_write_grace(cam_id) else None
        reachable, _ts = entry
        if not reachable and self._in_local_write_grace(cam_id):
            return True
        return reachable

    def is_updating(self, cam_id: str) -> bool:
        """True while firmware install is in progress for `cam_id`.

        Reads `firmware_cache[cam_id]['updating']` populated by the slow-tier
        firmware poll. The camera reboots during the install (typically 3-7 min)
        so dependent entities should flip to unavailable for that window. The
        camera-status sensor surfaces the same state as the enum value
        ``"updating"``.
        """
        return bool(self.firmware_cache.get(cam_id, {}).get("updating", False))

    async def async_local_tcp_ping(self, cam_id: str, timeout: float = 1.5) -> bool:
        """Quick TCP connect to camera port 443 on LAN — returns True if reachable.

        Tries rcp_lan_ip_cache first, falls back to local_creds_cache.
        Result is written to lan_tcp_reachable for stream pre-check reuse.
        Much faster than cloud /commissioned check (~5ms vs ~200ms).
        """
        cam_ip = self.get_cam_lan_ip(cam_id)
        if not cam_ip:
            return False  # no known LAN IP — can't ping locally
        # rcp_lan_ip_cache is populated from RCP data returned via the cloud
        # proxy and restored unvalidated from storage (unlike
        # local_creds_cache, whose host is validated at every write site) —
        # reject anything that isn't a private LAN address before opening a
        # TCP connection to it (Copilot review round 14).
        if not _is_safe_local_camera_host(f"{cam_ip}:443"):
            return False
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(cam_ip, 443),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            result = True
        except TimeoutError, OSError:
            result = False
        self.lan_tcp_reachable[cam_id] = (result, time.monotonic())
        return result

    async def async_outage_ping_all(self) -> None:
        """Ping every known camera concurrently during a cloud outage.

        Called from all three outer failure paths in `_async_update_data`
        (`UpdateFailed`/`TimeoutError`/`aiohttp.ClientError`, via
        tick_failure.py's dispatch_* helpers — Copilot review round 15).
        Throttled
        to once per 30 s so a flapping cloud does not hammer the LAN. Result
        feeds `lan_tcp_reachable`, which the switch/light entity
        `available` checks and the card LAN-tile renderer consult.
        """
        now = time.monotonic()
        if (now - self._last_outage_ping_at) < 30.0:
            return
        self._last_outage_ping_at = now
        cam_ids: list[str] = []
        if self.data:
            cam_ids.extend(self.data.keys())
        # Also include cams known only via LAN IP cache (rare — coordinator
        # data not yet populated after a fresh start mid-outage).
        for cid in self.rcp_lan_ip_cache:
            if cid not in cam_ids:
                cam_ids.append(cid)
        if not cam_ids:
            return
        results = await asyncio.gather(
            *(self.async_local_tcp_ping(cid) for cid in cam_ids),
            return_exceptions=True,
        )
        _ok = sum(1 for r in results if r is True)
        # DEBUG not INFO (Runde 2 P3 #7): throttled to once per 30s but only
        # while the cloud is down — a sustained outage (minutes to hours)
        # would otherwise spam INFO every 30s for the whole duration.
        _LOGGER.debug(
            "Outage LAN-ping: %d/%d cam(s) reachable (%s)",
            _ok,
            len(cam_ids),
            ", ".join(
                f"{cid[:8]}={'on' if r is True else 'off' if r is False else 'err'}"
                for cid, r in zip(cam_ids, results, strict=False)
            ),
        )
        # Notify dependent entities (binary_sensor.*_lan_reachable, privacy/light
        # switch `available` checks) so the new ping result reflects in the UI
        # without waiting for the next coordinator tick.
        self.async_update_listeners()

    def get_cam_lan_ip(self, cam_id: str) -> str | None:
        """Return the best known LAN IP for a camera, or None if not yet discovered."""
        ip = self.rcp_lan_ip_cache.get(cam_id)
        if ip:
            return ip
        creds = self.local_creds_cache.get(cam_id)
        return creds.get("host") if creds else None

    def should_check_status(
        self, cam_id: str, now: float, interval_status: int
    ) -> bool:
        """Determine if this camera needs a status check this tick.

        - Normal cameras: check every interval_status seconds.
        - Persistently offline cameras (>15 min): check every _OFFLINE_EXTENDED_INTERVAL.

        Uses per-camera timestamps (per_cam_status_at) instead of the global
        _last_status so that the check interval is independent of scan_interval.
        With _last_status, setting scan_interval < interval_status caused _last_status
        to advance every tick, making (now - _last_status) always < interval_status
        and status checks never firing after the first tick.
        """
        per_cam_last = self.per_cam_status_at.get(cam_id, -math.inf)
        offline_since = self.offline_since.get(cam_id)
        if offline_since and (now - offline_since) > self._OFFLINE_EXTENDED_INTERVAL:
            # Camera has been offline for a while — use extended interval
            return (now - per_cam_last) >= self._OFFLINE_EXTENDED_INTERVAL
        return (now - per_cam_last) >= interval_status

    # ── Main update ───────────────────────────────────────────────────────────
    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Coordinator tick — runs every scan_interval seconds.

        Each data type (status, events) is only re-fetched when its own
        interval has elapsed, reducing unnecessary API traffic.

        Returns dict keyed by cam_id:
          {
            "info":   {...},    # from GET /v11/video_inputs (every tick)
            "status": "ONLINE", # from ping — only when interval_status elapsed
            "events": [...],    # from events API — only when interval_events elapsed
            "live":   {...},    # cached proxy info from PUT /connection
          }
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session",
        # ...) working the same way it did before BoschCameraCoordinator
        # moved out of __init__.py — those patches target the package's own
        # namespace (kept local to avoid a module-level import cycle).
        token = self.token
        if not token and not self.refresh_token:
            # No token at all is not a transient condition UpdateFailed would
            # imply (endless SETUP_RETRY) — it means re-authentication is
            # required, so start the reauth flow instead (bug-hunt 2026-07-27,
            # Copilot review round 3).
            raise ConfigEntryAuthFailed(
                "Not authenticated — re-add the integration to log in"
            )

        opts = self.options
        now = time.monotonic()

        # Fast first tick: on startup, only fetch camera list + basic status.
        # Skip events + slow-tier to reduce startup from ~2 min to ~15s.
        # Full data loads on the second tick (60s later).
        is_first_tick = not self._first_tick_done
        if is_first_tick:
            self._first_tick_done = True

        # FCM push is not part of this minimal build — fcm_healthy stays
        # False forever, so the event poll always runs at the faster
        # push-not-delivering cadence below (never the relaxed interval).
        with self.fcm_lock:
            fcm_healthy = self.fcm_healthy
        if fcm_healthy:
            event_interval = int(opts.get("interval_events", 300))
        else:
            # FCM is not delivering (disabled or flagged unhealthy): the poll IS
            # the detection path now, so it must run faster than the motion
            # window or polled events age out before the binary sensor can see
            # them (issue #36). Cap at FCM_DOWN_EVENT_POLL_SEC; honour a user's
            # explicitly-lower interval_events via min().
            event_interval = min(
                int(opts.get("interval_events", 300)), int(FCM_DOWN_EVENT_POLL_SEC)
            )
        do_events = (now - self._last_events) >= event_interval
        do_slow = (now - self._last_slow) >= int(opts.get("interval_slow", 300))

        # First tick: skip heavy operations
        if is_first_tick:
            do_events = False
            do_slow = False
            _LOGGER.info(
                "Fast first tick — skipping events + slow-tier for quick startup"
            )

        session = await async_get_bosch_cloud_session(self.hass)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        try:
            # ── 1. List cameras (every tick — lightweight, needed for entity list) ──
            cam_list, token, headers = await fetch_camera_list(
                self, session, headers, token
            )

            # ── Feature flags (fetch once — rarely changes) ────────────────
            await ensure_feature_flags(self, session, headers)

            # ── Protocol version check (once at startup) ──────────────────
            await ensure_protocol_checked(self, session, headers)

            # ── Build camera ID list ─────────────────────────────────────────
            cam_ids: list[str] = []
            cam_by_id: dict[str, dict[str, Any]] = {}
            for cam in cam_list:
                cid = cam.get("id", "")
                if cid:
                    cam_ids.append(cid)
                    cam_by_id[cid] = cam
                    # Cache hardware version for model-specific behavior
                    self.hw_version[cid] = cam.get("hardwareVersion", "CAMERA")

            # ── 2. Status ─ parallel across all cameras ────────────────────────
            any_status_checked = await poll_statuses(
                self, cam_ids, session, headers, now, opts
            )

            # ── 3. Events — parallel across all cameras ──────────────────────
            any_events_fetched = await poll_events(
                self, cam_ids, session, headers, do_events
            )

            # ── Build data dict + process new events (must be sequential) ─────
            data = await build_data_and_dispatch(
                self, cam_ids, cam_by_id, now, do_events
            )

            # Update timestamps only after successful fetches
            if any_status_checked:
                self._last_status = now
            # Advance the events timestamp only when at least one camera returned
            # a definitive result. If every fetch failed (cloud blip), leave
            # _last_events so do_events stays True next tick and the poll retries
            # promptly instead of backing off a full interval (up to 300 s while
            # FCM is healthy). Cross-version parity with the ioBroker fix.
            if do_events and any_events_fetched:
                self._last_events = now
            if do_slow:
                self._last_slow = now

            # ── 4. Read privacy mode + light from cloud API response (primary) ──
            # Cloud API is ~10x faster than SHC local API (113ms vs 1122ms).
            # privacyMode and featureSupport are already in /v11/video_inputs —
            # no extra request needed. SHC (step 5) supplements as fallback.
            for cam_id_key, cam_entry in data.items():
                cam_raw = cam_entry.get("info", {})
                _poll_cam_info_caches(self, cam_id_key, cam_raw)

                # ── Per-camera context: hw/is_gen2/is_online/stream state/
                # slow-tier defer gate — computed once, shared by every
                # slow-tier sub-block below (replaces several redundant
                # re-derivations the original inline loop had at different
                # points) ──────────────────────────────────────────────────
                ctx = _compute_cam_context(
                    self, cam_id_key, cam_raw, data, opts, do_slow
                )
                is_online = ctx.is_online
                do_slow_cam = ctx.do_slow_cam

                # Pan position + Gen2 lighting/switch — both polled every
                # tick (not slow-tier-gated), only gated on is_online.
                await _poll_cam_control(self, cam_id_key, ctx, session, headers)

                # ── Slow tier: motion detection settings ──────────────────────
                # Only fetched every interval_slow seconds (default 5 min).
                await _poll_slow_tier_endpoints(
                    self,
                    cam_id_key,
                    cam_raw,
                    ctx,
                    data,
                    session,
                    headers,
                )

                # ── RCP data via cloud proxy (slow tier — every 5 min) ────────
                # Opens a proxy connection and reads multiple RCP values.
                # Only when camera is ONLINE and slow-tier interval elapsed.
                # Skip when Privacy is ON — the cloud proxy rejects RCP session
                # handshakes (invalid session 0x00000000) while privacy blocks the
                # camera's RCP endpoint. Avoids noisy debug logs every 5 min.
                privacy_on = ctx.privacy_on
                if is_online and do_slow_cam and privacy_on:
                    _LOGGER.debug(
                        "RCP slow-tier skipped for %s (privacy ON)", cam_id_key
                    )
                if is_online and do_slow_cam and not privacy_on:
                    try:
                        # Pooled Bosch-cloud session (cloud_ssl.py) — this
                        # slow-tier RCP fetch used to open a fresh
                        # TCPConnector+ClientSession per camera on every tick
                        # (Work Package 1, stream-perf-stability-refactor).
                        # Must NOT be closed here: it's process-wide, shared
                        # with every other Bosch-cloud call, and closed
                        # exactly once on EVENT_HOMEASSISTANT_STOP.
                        rcp_session = await async_get_bosch_cloud_session(self.hass)
                        rcp_headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        }
                        try:
                            async with asyncio.timeout(TIMEOUT_PUT_CONNECTION):
                                async with rcp_session.put(
                                    f"{CLOUD_API}/v11/video_inputs/{cam_id_key}/connection",
                                    json={
                                        "type": "REMOTE",
                                        "highQualityVideo": self.get_quality_params(
                                            cam_id_key
                                        )[0],
                                    },
                                    headers=rcp_headers,
                                ) as conn_resp:
                                    if conn_resp.status in (200, 201):
                                        conn_data = await conn_resp.json(
                                            content_type=None
                                        )
                                        urls = conn_data.get("urls", [])
                                        # urls[0] = "proxy-NN.live.cbs.boschsecurity.com:42090/{hash}"
                                        # _parse_safe_rcp_proxy_url rejects a
                                        # malformed/unsafe entry by returning
                                        # None (logs internally) — an
                                        # unvalidated proxy host here is an
                                        # SSRF path (bug-hunt 2026-07-27,
                                        # Copilot review round 5).
                                        parsed_proxy = (
                                            _parse_safe_rcp_proxy_url(
                                                urls[0], cam_id_key
                                            )
                                            if urls
                                            else None
                                        )
                                        if parsed_proxy:
                                            proxy_host, proxy_hash = parsed_proxy
                                            await self._async_update_rcp_data(
                                                cam_id_key, proxy_host, proxy_hash
                                            )
                                    else:
                                        _LOGGER.debug(
                                            "RCP proxy connection HTTP %d for %s",
                                            conn_resp.status,
                                            cam_id_key,
                                        )
                        except (TimeoutError, aiohttp.ClientError) as err:
                            _LOGGER.debug(
                                "RCP proxy connect error for %s: %s",
                                cam_id_key,
                                err,
                            )
                    except Exception as err:  # noqa: BLE001 — per-camera RCP update; one camera's protocol/parsing failure must not abort the slow-tier loop for the rest
                        _LOGGER.debug("RCP update skipped for %s: %s", cam_id_key, err)

            # ── 7/8. Housekeeping: stale devices, availability notify,
            # LAN-IP/hw-version/local-creds persistence, cloud-state notify ──
            await run_housekeeping(self, data, opts, now, is_first_tick)

            # Raise a Repairs issue when movement/person notifications are
            # disabled on a camera — without them the bosch_shc_camera_motion/
            # _person bus events never fire, with no error shown otherwise.
            try:
                self._refresh_notifications_disabled_issues()
            except Exception:
                _LOGGER.debug(
                    "Notifications-disabled Repairs check failed (non-fatal)",
                    exc_info=True,
                )

            # Raise a Repairs issue when a firmware update is available for a
            # camera — see _refresh_firmware_update_issues docstring.
            try:
                self._refresh_firmware_update_issues()
            except Exception:
                _LOGGER.debug(
                    "Firmware-update Repairs check failed (non-fatal)",
                    exc_info=True,
                )

            return data  # noqa: TRY300 — moving this to an `else` block would require restructuring the entire preceding try body, which spans the whole tick; the `except` clauses below only match specific exception types raised by earlier awaits, not this plain return

        except UpdateFailed:
            await dispatch_update_failed(self)
            raise
        except TimeoutError:
            timeout_exc = await dispatch_timeout(self)
            raise timeout_exc from None
        except aiohttp.ClientError as err:
            client_exc = await dispatch_client_error(self, err)
            raise client_exc from err

    def _refresh_notifications_disabled_issues(self) -> None:
        """Create or clear Repairs issues for cameras with disabled movement/person notifications.

        Called once per coordinator tick (inside _async_update_data) AFTER data is
        built.  Idempotent — safe to call every tick.

        A camera is only processed when its notifications dict is non-empty
        (i.e. the endpoint has been fetched at least once).  Cameras with no
        notification data yet are skipped entirely to avoid false-positive
        issues on startup.
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.ir", ...) working the same
        # way it did before BoschCameraCoordinator moved out of __init__.py

        for cam_id, notif in self.notifications_cache.items():
            if not notif:
                # No data fetched yet — skip to avoid false positives.
                continue

            disabled = [t for t in ("movement", "person") if notif.get(t) is False]

            if disabled:
                cam_title: str = (
                    (self.data or {})
                    .get(cam_id, {})
                    .get("info", {})
                    .get("title", cam_id)
                )
                types_str = " + ".join(t.capitalize() for t in disabled)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"notifications_disabled_{cam_id}",
                    is_fixable=False,
                    is_persistent=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="notifications_disabled",
                    translation_placeholders={
                        "camera": cam_title,
                        "types": types_str,
                    },
                )
                if cam_id not in self._notif_disabled_logged:
                    self._notif_disabled_logged.add(cam_id)
                    _LOGGER.warning(
                        "Camera %r has %s cloud notification(s) disabled — "
                        "the corresponding bosch_shc_camera_* event(s) will "
                        "never fire. Enable the notification setting(s) in "
                        "the Bosch Smart Home app",
                        cam_title,
                        types_str,
                    )
            else:
                ir.async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"notifications_disabled_{cam_id}",
                )
                self._notif_disabled_logged.discard(cam_id)

    def _refresh_firmware_update_issues(self) -> None:
        """Log once per camera when a firmware update becomes available.

        Called once per coordinator tick (inside _async_update_data) AFTER
        data is built. Idempotent — safe to call every tick. Does NOT raise
        a Repairs issue: Bosch installs camera firmware automatically on its
        own schedule with no action available for the user to take here (no
        `update`/Repairs fix-flow platform exists in this snapshot-only
        build), so a Repairs issue for it would be non-actionable — exactly
        the class of issue HA's Repairs guidelines rule out (bug-hunt
        2026-07-27, Copilot review round 6). The one-time INFO log below is
        the informational signal instead.

        A camera is only processed once its firmware endpoint has been fetched
        at least once (`firmware_cache[cam_id]['upToDate']` present) to avoid
        a false-positive "cleared" transition on startup.
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.ir", ...) working the same
        # way it did before BoschCameraCoordinator moved out of __init__.py

        for cam_id, fw in self.firmware_cache.items():
            if not fw:
                # No data fetched yet — skip to avoid false positives.
                continue

            up_to_date = fw.get("upToDate")  # codespell:ignore
            if up_to_date is None:
                continue

            if not up_to_date:
                if cam_id not in self._fw_update_alerted:
                    cam_title: str = (
                        (self.data or {})
                        .get(cam_id, {})
                        .get("info", {})
                        .get("title", cam_id)
                    )
                    current = fw.get("current") or "?"
                    latest = fw.get("update") or "?"
                    self._fw_update_alerted.add(cam_id)
                    _LOGGER.info(
                        "Firmware update available for %r: %s -> %s",
                        cam_title,
                        current,
                        latest,
                    )
            else:
                self._fw_update_alerted.discard(cam_id)

    def _persist_cloud_outage_flag(self) -> None:
        """Persist the cloud-outage-notified dedup flag.

        So a restart mid-outage doesn't re-fire "Cloud nicht erreichbar".
        """
        store = getattr(self, "cloud_alert_store", None)
        if store is None:
            return
        # Tracked (not a bare hass.async_create_task) — an untracked save
        # can still complete after config-entry removal deletes the Store,
        # recreating integration-owned state on disk after removal and
        # bypassing the teardown behavior spawn_tracked() documents
        # (Copilot review round 10).
        self.spawn_tracked(
            store.async_save({"outage_notified": bool(self.cloud_outage_notified)}),
            name="bosch_shc_camera_persist_cloud_outage_flag",
        )

    async def _async_maybe_announce_camera_status(
        self,
        cam_id: str,
        new_status: str,
    ) -> None:
        """Fire a notification when a camera flips between online and offline.

        The first observation per camera is silent — we record the baseline
        without notifying so a HA restart while a camera is offline does not
        re-announce the existing state. Only `online → offline` and
        `offline → online` transitions notify; `unknown` is treated as a
        non-event (camera info is just temporarily missing, not a real
        availability change).

        Routing: `_alert_services()` reads the `alert_notify_service`
        option. Notify failures are swallowed.
        """
        # Lazy-init for SimpleNamespace test stubs that bypass __init__.
        if not hasattr(self, "_offline_seen_at"):
            self._offline_seen_at = {}
        last = self._last_camera_status.get(cam_id)
        if last is None:
            # First tick after startup — record baseline silently.
            self._last_camera_status[cam_id] = new_status
            return
        # Whenever the camera is currently online, drop any pending offline-grace
        # timer (covers recovery within the grace window AND the no-op
        # online→online tick below).
        if new_status == "online":
            self._offline_seen_at.pop(cam_id, None)
        if new_status == last:
            return
        # Skip transitions involving "unknown" — coordinator hickups can flap
        # status to UNKNOWN for one tick during cloud transients; do not
        # convert that into spam.
        if new_status == "unknown" or last == "unknown":
            self._last_camera_status[cam_id] = new_status
            return
        # Offline-announce grace: a camera on a Wi-Fi repeater/mesh briefly drops
        # during a repeater restart or DFS channel change and recovers within a
        # minute or two. Only announce offline once it has stayed offline for
        # CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC; a recovery within the window is
        # silent. We hold the baseline at "online" (don't commit the flip) until
        # the grace elapses, so the eventual recovery doesn't emit a spurious
        # "online" notification either.
        if new_status == "offline":
            seen = self._offline_seen_at.get(cam_id)
            now_mono = time.monotonic()
            if seen is None:
                self._offline_seen_at[cam_id] = now_mono
                return
            if (now_mono - seen) < CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC:
                return
        self._last_camera_status[cam_id] = new_status
        services = self._alert_services()
        cam_info = self.data.get(cam_id, {}).get("info", {})
        cam_name = cam_info.get("title") or cam_id[:8]
        if not services:
            _LOGGER.debug(
                "Camera status announce skipped for %s (%s→%s): no notify service configured",
                cam_name,
                last,
                new_status,
            )
            return
        if new_status == "offline":
            title = f"Bosch Kamera {cam_name} offline"
            message = (
                f"Bosch Kamera {cam_name} ist offline. "  # codespell:ignore
                "Live-Bild und Snapshots sind bis zur Wiederverbindung nicht verfügbar."
            )
        else:
            title = f"Bosch Kamera {cam_name} wieder online"
            message = (
                f"Bosch Kamera {cam_name} ist wieder erreichbar."  # codespell:ignore
            )
        for svc in services:
            try:
                data = {"message": message, "title": title}
                # `alert_notify_service` stores entries like `notify.<svc>`
                # OR bare service names `<svc>`.
                _domain, _service = svc.split(".", 1) if "." in svc else ("notify", svc)
                await self.hass.services.async_call(
                    _domain, _service, data, blocking=False
                )
                _LOGGER.info(
                    "Camera status announce sent via notify.%s for %s (%s→%s)",
                    svc,
                    cam_name,
                    last,
                    new_status,
                )
            except Exception as exc:  # noqa: BLE001 — per-notify-target loop; one target's failure (unknown service, arbitrary integration internals) must not skip remaining configured notify services
                _LOGGER.warning(
                    "Camera status announce via notify.%s for %s failed: %s",
                    svc,
                    cam_name,
                    exc,
                )

    async def _async_handle_session_quota_hit(self, cam_id: str) -> None:
        """Track HTTP 444 hits per camera and fire a persistent notification if repeated.

        After _SESSION_QUOTA_NOTIFY_THRESHOLD (3) hits within _SESSION_QUOTA_WINDOW_S (5 min)
        a HA persistent_notification is created advising the user to close other clients.
        Non-fatal — any failure is swallowed so the caller's status update is unaffected.
        """
        try:
            now = time.monotonic()
            hits = self._session_quota_hits.setdefault(cam_id, [])
            # Prune hits outside the window
            hits[:] = [t for t in hits if (now - t) < self._SESSION_QUOTA_WINDOW_S]
            hits.append(now)

            if len(hits) >= self._SESSION_QUOTA_NOTIFY_THRESHOLD:
                cam_info = (
                    self.data.get(cam_id, {}).get("info", {}) if self.data else {}
                )
                cam_name = cam_info.get("title") or cam_id[:8]
                notification_id = f"bosch_session_quota_{cam_id[:8].lower()}"
                title = f"Bosch Kamera {cam_name}: Sitzungslimit erreicht"
                message = (
                    f"Kamera {cam_name} meldet HTTP 444 (Session-Quota). "
                    "Zu viele gleichzeitige Live-Verbindungen im Bosch-Konto. "
                    "Bitte schließen Sie die Bosch App auf weiteren Geräten "  # codespell:ignore
                    "oder deaktivieren Sie parallele Integrationen (ioBroker, Python CLI). "  # codespell:ignore
                    "Die Integration wiederholt den Verbindungsaufbau automatisch."
                )
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message,
                        "notification_id": notification_id,
                    },
                    blocking=False,
                )
                _LOGGER.warning(
                    "Session-quota persistent notification created for %s (%d hits in %.0fs)",
                    cam_id[:8],
                    len(hits),
                    self._SESSION_QUOTA_WINDOW_S,
                )
        except Exception as exc:  # noqa: BLE001 — explicitly non-fatal per docstring/log message; must not affect the caller's status update
            _LOGGER.debug("Session-quota notification failed (non-fatal): %s", exc)

    async def _async_maybe_announce_cloud_state(self, success: bool) -> None:
        """Fire a user notification on cloud-reachability transitions.

        Outage path: when ``success=False`` for at least
        ``_CLOUD_OUTAGE_NOTIFY_AFTER_S`` seconds in a row, fire a one-shot
        "Bosch Cloud nicht erreichbar" notification. Recovery path: when the
        next ``success=True`` arrives after an outage was announced, fire
        "Bosch Cloud wieder erreichbar". One-tick failure blips never get
        announced — they self-clear on the next success.

        Routing: `_alert_services()` reads the `alert_notify_service`
        option. Notify failures are swallowed.
        """
        now = time.monotonic()
        if success:
            if not self.cloud_outage_notified:
                # Was either healthy already or in a sub-grace blip — just
                # reset the tracker so the next outage starts a fresh window.
                self._cloud_outage_started_at = None
                return
            # We previously announced an outage — announce recovery now.
            self.cloud_outage_notified = False
            self._cloud_outage_started_at = None
            getattr(self, "_persist_cloud_outage_flag", lambda: None)()
            await self._async_dispatch_cloud_alert(recovered=True)
            return
        # success=False
        if self._cloud_outage_started_at is None:
            self._cloud_outage_started_at = now
            return
        if self.cloud_outage_notified:
            return
        if (now - self._cloud_outage_started_at) < self._CLOUD_OUTAGE_NOTIFY_AFTER_S:
            return
        # Outage has persisted long enough → announce.
        self.cloud_outage_notified = True
        getattr(self, "_persist_cloud_outage_flag", lambda: None)()
        await self._async_dispatch_cloud_alert(recovered=False)

    async def _async_dispatch_cloud_alert(self, *, recovered: bool) -> None:
        """Send the actual notification through the integration's alert pipeline."""
        services = self._alert_services()
        if not services:
            _LOGGER.debug(
                "Cloud-state alert skipped (recovered=%s) — no notify service configured",
                recovered,
            )
            return
        if recovered:
            title = "Bosch Cloud wieder erreichbar"
            message = (
                "Die Bosch-Cloud antwortet wieder. "
                "Snapshots und Stream-Anfragen laufen normal."
            )
        else:
            title = "Bosch Cloud nicht erreichbar"
            message = (
                "Die Bosch-Cloud antwortet nicht mehr (HTTP 5xx / Timeout). "
                "Privacy- und Licht-Schalter gehen weiter über LAN, "
                "Snapshots und Stream-Anfragen sind eingeschränkt."
            )
        for svc in services:
            try:
                data = {"message": message, "title": title}
                # `alert_notify_service` stores entries like `notify.<svc>`
                # OR bare service names `<svc>`.
                _domain, _service = svc.split(".", 1) if "." in svc else ("notify", svc)
                await self.hass.services.async_call(
                    _domain, _service, data, blocking=False
                )
                _LOGGER.info(
                    "Cloud-state alert sent via notify.%s (recovered=%s)",
                    svc,
                    recovered,
                )
            except Exception as exc:  # noqa: BLE001 — per-notify-target loop; one target's failure must not skip remaining configured notify services
                _LOGGER.warning(
                    "Cloud-state alert via notify.%s failed: %s",
                    svc,
                    exc,
                )

    def _compute_status_for(
        self,
        cam_id: str,
        cam_data: dict[str, Any] | None = None,
    ) -> str:
        """Reuse the BoschCameraStatusSensor logic so the announce path and sensor never drift apart.

        Mirror of `sensor.BoschCameraStatusSensor.native_value`: cloud ONLINE
        + latest event TROUBLE_DISCONNECT → offline; otherwise the cloud
        status verbatim. The `cam_data` argument lets the update-loop pass
        the fresh data dict before `self.data` has been swapped by the
        parent class (`_async_update_data` returns after the per-cam
        transition check fires).
        """
        if cam_data is None:
            cam_data = self.data.get(cam_id, {}) if self.data else {}
        raw = str(cam_data.get("status", "UNKNOWN")).lower()
        if raw == "online":
            events = cam_data.get("events", [])
            if (
                events
                and str(events[0].get("eventType", "")).upper() == "TROUBLE_DISCONNECT"
            ):
                return "offline"
        return raw

    # ── Per-cam_id dict/set purge (Runde 2 P1 #1) ──────────────────────────
    # `cleanup_stale_devices` below only removed the device-registry entry
    # for a camera that disappeared from the Bosch cloud account — none of
    # the ~100 per-cam_id-keyed coordinator dict/set attributes accumulated
    # over this coordinator instance's lifetime were ever cleared. On a
    # camera swap/rename (new cam_id, old one gone for good) those entries
    # just sit there forever, growing unbounded over the coordinator's
    # lifetime (never restarted except on HA restart/reload). This list is
    # audited against `BoschCameraCoordinator.__init__` — every attribute
    # there whose declared comment/usage confirms it is keyed by the plain
    # cam_id string lives in one of the two tuples below; anything NOT
    # listed here was deliberately excluded (see the comment block at the
    # end) and should stay that way unless its keying changes.
    #
    # Plain `dict[str, ...]` attributes keyed directly by cam_id → `.pop()`.
    _PURGE_CAM_DICT_ATTRS: tuple[str, ...] = (
        "audio_enabled",
        "audio_volume",
        "camera_entities",
        "image_entities",
        "slow_tier_defer_since",
        "cached_status",
        "cloud_444_at",
        "cached_events",
        "shc_state_cache",
        "pan_cache",
        "wifiinfo_cache",
        "ambient_light_cache",
        "rcp_dimmer_cache",
        "rcp_privacy_cache",
        "rcp_clock_offset_cache",
        "rcp_lan_ip_cache",
        "rcp_product_name_cache",
        "rcp_bitrate_cache",
        "rcp_alarm_catalog_cache",
        "rcp_motion_zones_cache",
        "rcp_motion_coords_cache",
        "rcp_tls_cert_cache",
        "rcp_network_services_cache",
        "rcp_iva_catalog_cache",
        "_rcp_state_cache",
        "_rcp_cmd_failures",
        "_quality_preference",
        "_proxy_url_cache",
        "_rcp_099e_probe_failed_until",
        "_fresh_snap_cache",
        "last_event_ids",
        "unread_events_cache",
        "privacy_sound_cache",
        "commissioned_cache",
        "firmware_cache",
        "timestamp_cache",
        "ledlights_cache",
        "lens_elevation_cache",
        "audio_cache",
        "motion_light_cache",
        "image_rotation_180",
        "external_stream_enabled",
        "ambient_lighting_cache",
        "lighting_switch_cache",
        "global_lighting_cache",
        "notifications_cache",
        "rules_cache",
        "cloud_zones_cache",
        "cloud_privacy_masks_cache",
        "lighting_options_cache",
        "intrusion_config_cache",
        "audio_detection_cache",
        "alarm_settings_cache",
        "alarm_status_cache",
        "_last_alarm_type",
        "arming_cache",
        "icon_led_brightness_cache",
        "gen2_zones_cache",
        "gen2_private_areas_cache",
        "_user_token_cache",
        "hw_version",
        "lan_tcp_reachable",
        "local_write_at",
        "local_creds_cache",
        "offline_since",
        "per_cam_status_at",
        "_last_camera_status",
        "_session_quota_hits",
        "light_set_at",
        "notif_set_at",
        "privacy_set_at",
        "privacy_sound_set_at",
        "timestamp_set_at",
        "ledlights_set_at",
        "arming_set_at",
        "intrusion_config_set_at",
        "audio_detection_set_at",
        "motion_set_at",
        "alarm_settings_set_at",
        "lighting_options_set_at",
        "_offline_seen_at",
        "_snapshot_fetch_locks",
        "_fresh_snap_locks",
    )
    # `set[str]` attributes whose members are cam_id → `.discard()`.
    _PURGE_CAM_SET_ATTRS: tuple[str, ...] = (
        "slow_tier_deferred",
        "_notif_disabled_logged",
        "_fw_update_alerted",
    )
    # Deliberately EXCLUDED (audited, not an oversight):
    #   rcp_session_cache / rcp_session_locks — keyed by proxy_hash, not cam_id.
    #   alert_sent_ids — keyed by event_id, not cam_id.
    #   feature_flags — account-level (GET /v11/feature_flags once), not per-cam.
    #   Everything else in __init__ not listed above is a genuinely global/
    #   account-level attribute (counters, constants, locks keyed by
    #   proxy_hash, single Task/Store handles, etc.) — not per-cam.

    def _purge_cam_id(self, cam_id: str) -> None:
        """Purge every per-cam_id coordinator dict/set entry for `cam_id`.

        Called from `cleanup_stale_devices` once a camera has been
        confirmed gone from the Bosch cloud account (device-registry entry
        already removed). See `_PURGE_CAM_DICT_ATTRS` /
        `_PURGE_CAM_SET_ATTRS` above for the audited attribute list.
        """
        for attr_name in self._PURGE_CAM_DICT_ATTRS:
            attr = getattr(self, attr_name)
            attr.pop(cam_id, None)
        for attr_name in self._PURGE_CAM_SET_ATTRS:
            attr = getattr(self, attr_name)
            attr.discard(cam_id)

    def cleanup_stale_devices(self, current_cam_ids: set[str]) -> None:
        """Remove devices for cameras no longer in the Bosch cloud account.

        Quality-Scale Gold rule `stale-devices`. Compares the device registry
        against the freshly-fetched camera list — anything tied to our domain
        with a cam_id that disappeared gets removed (entities + device entry).
        Without this, a camera removed from the Bosch app stays visible in HA
        as `unavailable` forever. Also purges every per-cam_id coordinator
        dict/set entry for the removed camera (see `_purge_cam_id`) so those
        do not grow unbounded across camera swaps/renames over the lifetime
        of this coordinator instance.
        """
        dev_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            cam_id = next(
                (ident[1] for ident in device.identifiers if ident[0] == DOMAIN),
                None,
            )
            if cam_id and cam_id not in current_cam_ids:
                _LOGGER.info(
                    "Removing stale device for camera %s (no longer in Bosch cloud account)",
                    cam_id[:8],
                )
                dev_reg.async_remove_device(device.id)
                self._purge_cam_id(cam_id)

    def _get_rcp_session_lock(self, proxy_hash: str) -> asyncio.Lock:
        """Get or create per-proxy_hash RCP session-open lock."""
        return get_or_create_lock(self.rcp_session_locks, proxy_hash)

    async def async_fetch_live_snapshot(
        self, cam_id: str, jpeg_size: int | None = None
    ) -> bytes | None:
        """Open a temporary REMOTE proxy connection to fetch a fresh snap.jpg.

        Used by background image refresh so cameras always show a current
        image rather than a (possibly expired) event snapshot.

        ``jpeg_size`` overrides snap.jpg's resolution for callers that only need
        a preview (see const.jpeg_size_for_width). The default of ``None`` keeps
        JPEG_SIZE_FULL, so the background refresh, the image.* entity and the
        AI-analysis fetch — everything that persists or analyses the frame —
        are unaffected.

        Proxy URL caching: PUT /connection takes ~1.5s. The resulting proxy lease
        lasts ~60s. We cache urls[0] for 50s and skip PUT /connection on warm
        refreshes, reducing latency from ~3s → ~0.5s per card refresh cycle.

        Per-camera lock: concurrent callers (first-load + proactive refresh,
        Lovelace double-firing) are serialized so only one PUT /connection
        runs per camera at a time. The second caller finds the warm cache.
        """
        lock = get_or_create_lock(self._snapshot_fetch_locks, cam_id)
        async with lock:
            return await self._async_fetch_live_snapshot_impl(cam_id, jpeg_size)

    async def _async_fetch_live_snapshot_impl(
        self, cam_id: str, jpeg_size: int | None = None
    ) -> bytes | None:
        snap_jpeg_size = jpeg_size or JPEG_SIZE_FULL

        token = self.token
        if not token:
            return None
        # Privacy short-circuit: when privacy mode is ON, the camera returns
        # snap.jpg with HTTP 200 and 0 bytes (camera blocks live frames while
        # the shutter / privacy mask is engaged). Skip the network call entirely
        # rather than burning a PUT /connection + snap.jpg round-trip every
        # coordinator tick (~5-8 calls per minute across 4 cameras) just to
        # log "empty response (privacy mode ON?)" each time. The camera entity
        # falls back to its cached frame or _PLACEHOLDER_JPEG. Detected via the
        # cached `privacy_mode` boolean populated in the same /v11/video_inputs
        # response (line 1386) — no extra request needed.
        # shc_state_cache is always initialized to {} in __init__ (line 300),
        # so the old getattr() guard for AttributeError is no longer needed.
        # Previous hotfix used _camera_status_extra (wrong attr — never assigned),
        # so the privacy short-circuit never fired; fixed here.
        if self.shc_state_cache.get(cam_id, {}).get("privacy_mode"):
            return None

        # Reuse the pooled, application-lifetime Bosch cloud session instead of
        # opening a fresh TCP+TLS connection on every snapshot poll (~5-8 calls/
        # min across 4 cameras). Connection pooling removes a full TLS handshake
        # per tick. The CM does NOT close the shared session. 2026-06-18 (perf).
        async with async_bosch_cloud_session_cm(self.hass) as session:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            conn_url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/connection"

            async def _get_proxy_url_entry() -> str | None:
                """Return a valid urls[0] string, using cache when possible."""
                now = time.monotonic()
                cached = self._proxy_url_cache.get(cam_id)
                if cached:
                    url_entry, expires_at = cached
                    if now < expires_at:
                        _LOGGER.debug(
                            "fetch_live_snapshot: proxy cache HIT for %s (%.0fs remaining)",
                            cam_id,
                            expires_at - now,
                        )
                        return url_entry
                    del self._proxy_url_cache[cam_id]

                # Cache miss — call PUT /connection
                async with asyncio.timeout(TIMEOUT_PUT_CONNECTION):
                    async with session.put(
                        conn_url,
                        json={
                            "type": "REMOTE",
                            "highQualityVideo": self.get_quality_params(cam_id)[0],
                        },
                        headers=headers,
                    ) as resp:
                        if resp.status not in (200, 201):
                            _LOGGER.debug(
                                "fetch_live_snapshot: PUT /connection → HTTP %d for %s",
                                resp.status,
                                cam_id,
                            )
                            return None
                        result = _json.loads(await resp.text())
                        urls = result.get("urls", [])
                        if not urls:
                            return None
                        self._proxy_url_cache[cam_id] = (urls[0], now + 50.0)  # 50s TTL
                        _LOGGER.debug(
                            "fetch_live_snapshot: proxy cache MISS for %s — PUT /connection done",
                            cam_id,
                        )
                        return str(urls[0])

            try:
                url_entry = await _get_proxy_url_entry()
                if not url_entry:
                    return None
                # Validate the host portion before it's used to build any
                # request URL (RCP 0x099e below, or the snap.jpg fetch
                # further down) — an unvalidated proxy host from Bosch's
                # own PUT /connection response is an SSRF path (bug-hunt
                # 2026-07-27, Copilot review round 5).
                _entry_host = url_entry.split("/", 1)[0]
                if not _is_safe_bosch_host(_entry_host):
                    _LOGGER.warning(
                        "Rejected unsafe RCP proxy host for %s: %s",
                        cam_id,
                        _entry_host[:60],
                    )
                    return None

                # ── RCP 0x099e: 320x180 JPEG (Gen1 only) ──
                # Gen1 (INDOOR/OUTDOOR/CAMERA_360) returns a JPEG via the proxy RCP
                # endpoint. Gen2 (HOME_Eyes_*) responds with non-JPEG payload —
                # 0x0a88 only reports the *configured* snapshot resolution, not that
                # 0x099e delivers bytes. Skip on Gen2 to silence log noise; snap.jpg
                # works uniformly.
                # Defensive getattr — hw_version is a real-coordinator attribute
                # set in __init__, but tests use ``SimpleNamespace`` stubs that
                # don't auto-populate dicts. Without the fallback every snapshot
                # test (~14 cases across test_init_round7, test_init_sprint_*)
                # raises AttributeError before reaching the gate logic.
                hw_gen2 = getattr(self, "hw_version", {}).get(cam_id, "") in (
                    "HOME_Eyes_Indoor",
                    "HOME_Eyes_Outdoor",
                )
                parts = url_entry.split("/", 1)
                probe_failed_until = self._rcp_099e_probe_failed_until.get(
                    cam_id, -math.inf
                )
                probe_memoized_failed = time.monotonic() < probe_failed_until
                # RCP 0x099e only ever returns a fixed 320x180 JPEG — must
                # never be used to satisfy a full-resolution request (the
                # default jpeg_size=None), or camera.py would cache this
                # thumbnail as the shared full-res frame (bug-hunt
                # 2026-07-27, Copilot review round 3).
                if (
                    jpeg_size is not None
                    and len(parts) == 2
                    and not hw_gen2
                    and not probe_memoized_failed
                ):
                    proxy_host_rcp, proxy_hash_rcp = parts[0], parts[1]
                    rcp_base = f"https://{proxy_host_rcp}/{proxy_hash_rcp}/rcp.xml"
                    try:
                        # GitHub #56: hard-cap the probe — on cameras where it
                        # always fails (observed 2-8s per attempt, no timeout
                        # of its own), an unbudgeted probe starved the
                        # snap.jpg leg below of the time it needed to succeed.
                        async with asyncio.timeout(TIMEOUT_RCP_099E_PROBE):
                            session_id = await self.get_cached_rcp_session(
                                proxy_host_rcp, proxy_hash_rcp
                            )
                            raw = (
                                await self.rcp_read(rcp_base, "0x099e", session_id)
                                if session_id
                                else None
                            )
                        if raw and raw[:2] == b"\xff\xd8":
                            _LOGGER.debug(
                                "fetch_live_snapshot: RCP 0x099e → %d bytes (320x180 JPEG) for %s",
                                len(raw),
                                cam_id,
                            )
                            self._rcp_099e_probe_failed_until.pop(cam_id, None)
                            return raw
                        _LOGGER.debug(
                            "fetch_live_snapshot: RCP 0x099e unavailable for %s — using snap.jpg",
                            cam_id,
                        )
                        if session_id:
                            # Only memoize when we actually got a session and
                            # read a real (non-JPEG) response — a genuine
                            # signal this camera can't satisfy 0x099e. A
                            # missing session_id can be a transient
                            # session-acquisition hiccup (e.g. concurrent
                            # LOCAL-session contention) unrelated to hardware
                            # capability, so it must not disable the fast
                            # path for a full hour on a one-off blip.
                            self._rcp_099e_probe_failed_until[cam_id] = (
                                time.monotonic() + RCP_099E_PROBE_FAILURE_MEMO_SEC
                            )
                    except Exception as _rcp_err:  # noqa: BLE001 — custom RCP protocol layer (session acquisition + binary parsing); any failure must fall back to snap.jpg, not break snapshot fetch
                        _LOGGER.debug(
                            "fetch_live_snapshot: RCP error for %s: %s — using snap.jpg",
                            cam_id,
                            _rcp_err,
                        )
                        self._rcp_099e_probe_failed_until[cam_id] = (
                            time.monotonic() + RCP_099E_PROBE_FAILURE_MEMO_SEC
                        )
                elif len(parts) == 2 and not hw_gen2 and probe_memoized_failed:
                    _LOGGER.debug(
                        "fetch_live_snapshot: RCP 0x099e memoized-failed for %s — skipping probe, using snap.jpg",
                        cam_id,
                    )

                proxy_url = f"https://{url_entry}/snap.jpg?JpegSize={snap_jpeg_size}"
                async with asyncio.timeout(TIMEOUT_SNAP):
                    async with session.get(proxy_url) as snap_resp:
                        ct = snap_resp.headers.get("Content-Type", "")
                        if snap_resp.status == 404:
                            # Proxy URL expired — invalidate cache and retry once with a fresh lease
                            _LOGGER.debug(
                                "fetch_live_snapshot: snap.jpg 404 for %s — proxy URL expired, retrying",
                                cam_id,
                            )
                            self._proxy_url_cache.pop(cam_id, None)
                            url_entry2 = await _get_proxy_url_entry()
                            if not url_entry2:
                                return None
                            if not _is_safe_bosch_host(url_entry2.split("/", 1)[0]):
                                _LOGGER.warning(
                                    "Rejected unsafe RCP proxy host for %s (retry)",
                                    cam_id,
                                )
                                return None
                            proxy_url2 = f"https://{url_entry2}/snap.jpg?JpegSize={snap_jpeg_size}"
                            async with asyncio.timeout(TIMEOUT_SNAP):
                                async with session.get(proxy_url2) as snap_resp2:
                                    ct2 = snap_resp2.headers.get("Content-Type", "")
                                    if snap_resp2.status == 200 and "image" in ct2:
                                        data2: bytes = await snap_resp2.read()
                                        if data2:
                                            return data2
                            return None
                        if snap_resp.status == 200 and "image" in ct:
                            data: bytes = await snap_resp.read()
                            # Bosch returns HTTP 200 with 0 bytes when privacy mode is ON.
                            # F2 (2026-05-25): cross-check the camera's "privacy is on"
                            # signal against HA's cached privacy state — if HA still thinks
                            # privacy is OFF, we have a state drift (toggled in the Bosch
                            # app, not yet reflected via cloud poll) and emit a WARNING.
                            if not data:
                                cam_raw = self.data.get(cam_id, {})
                                ha_privacy_on = (
                                    str(cam_raw.get("privacyMode", "")).upper() == "ON"
                                )
                                if ha_privacy_on:
                                    _LOGGER.debug(
                                        "fetch_live_snapshot: %s → empty response (privacy mode ON, HA agrees)",
                                        cam_id,
                                    )
                                else:
                                    _LOGGER.warning(
                                        "Empty snapshot response for %s but HA "
                                        "privacy state is OFF — state drift (likely toggled "
                                        "via Bosch app, cloud poll lag), forcing refresh",
                                        cam_id,
                                    )
                                    # Actually force the refresh the message
                                    # promises: pull fresh privacy state from the
                                    # cloud now instead of waiting up to a full
                                    # poll interval. Without this the switch stays
                                    # visually wrong and this WARNING repeats on
                                    # every snapshot until the next poll. The
                                    # coordinator debouncer coalesces repeats.
                                    # Tracked (not a bare hass.async_create_task)
                                    # — otherwise this can outlive config-entry
                                    # unload and keep running against an
                                    # already-torn-down coordinator (Copilot
                                    # review round 12).
                                    self.spawn_tracked(
                                        self.async_request_refresh(),
                                        name="bosch_shc_camera_privacy_drift_refresh",
                                    )
                                return None
                            _LOGGER.debug(
                                "fetch_live_snapshot: %s → %d bytes", cam_id, len(data)
                            )
                            return data
                        _LOGGER.debug(
                            "fetch_live_snapshot: snap.jpg → HTTP %d for %s",
                            snap_resp.status,
                            cam_id,
                        )
                        return None

            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug("fetch_live_snapshot error for %s: %s", cam_id, err)
                return None

    async def async_fetch_fresh_event_snapshot(self, cam_id: str) -> bytes | None:
        """Fetch fresh events from Bosch API and return the latest event JPEG.

        Used as fallback for cameras whose snap.jpg returns 401 (e.g. CAMERA_360).
        Bypasses the coordinator's cached event list — always hits Bosch API directly
        so the returned imageUrl is always fresh (not expired).

        Concurrent callers for the same cam_id are coalesced: the first caller
        acquires the per-camera lock, fetches, and stores the result in
        `_fresh_snap_cache`; subsequent callers that arrive while the first is
        in-flight wait on the lock and then return the cached result without an
        additional network round-trip. This prevents 8+ duplicate cloud requests
        after an FCM push wakes all HA consumers simultaneously.
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session",
        # ...) working the same way it did before BoschCameraCoordinator
        # moved out of __init__.py — those patches target the package's own
        # namespace (kept local to avoid a module-level import cycle).
        # Fast path: cache hit without acquiring the lock (hot path after first fetch)
        cached = self._fresh_snap_cache.get(cam_id)
        if cached:
            data, expiry = cached
            if time.monotonic() < expiry:
                return data

        token = self.token
        if not token:
            return None

        # Slow path: serialise concurrent fetches for the same camera
        lock = get_or_create_lock(self._fresh_snap_locks, cam_id)
        async with lock:
            # Re-check cache now that we hold the lock — a concurrent caller that
            # raced through the fast-path miss and waited here may have already
            # populated the cache while we were queued.
            cached = self._fresh_snap_cache.get(cam_id)
            if cached:
                data, expiry = cached
                if time.monotonic() < expiry:
                    return data

            session = await async_get_bosch_cloud_session(self.hass)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            events_url = f"{CLOUD_API}/v11/events?videoInputId={cam_id}"

            try:
                async with asyncio.timeout(15):
                    async with session.get(events_url, headers=headers) as resp:
                        if resp.status != 200:
                            _LOGGER.debug(
                                "fetch_fresh_event_snapshot: events HTTP %d for %s",
                                resp.status,
                                cam_id,
                            )
                            return None
                        events = _json.loads(await resp.text())

                if not events:
                    return None

                # Try each event URL from newest to oldest
                img_headers = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
                for ev in events:
                    img_url = ev.get("imageUrl")
                    if not img_url:
                        continue
                    if not _is_safe_bosch_url(img_url):
                        _LOGGER.warning("Unsafe imageUrl rejected: %s", img_url[:60])
                        continue
                    try:
                        async with asyncio.timeout(20):
                            # allow_redirects=False: _is_safe_bosch_url only
                            # validates img_url itself — aiohttp follows
                            # redirects by default, so a validated URL could
                            # still redirect to an arbitrary internal host
                            # (bug-hunt 2026-07-27, Copilot review round 6 —
                            # same fix already applied to camera.py's
                            # equivalent event-snapshot fetch).
                            async with session.get(
                                img_url, headers=img_headers, allow_redirects=False
                            ) as snap_resp:
                                if snap_resp.status == 200:
                                    evdata: bytes = await snap_resp.read()
                                    if evdata:
                                        _LOGGER.debug(
                                            "fetch_fresh_event_snapshot: %s → %d bytes @ %s",
                                            cam_id,
                                            len(evdata),
                                            ev.get("timestamp", "")[:19],
                                        )
                                        self._fresh_snap_cache[cam_id] = (
                                            evdata,
                                            time.monotonic() + _FRESH_SNAP_TTL,
                                        )
                                        return evdata
                    except TimeoutError, aiohttp.ClientError:
                        continue

            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug(
                    "fetch_fresh_event_snapshot error for %s: %s", cam_id, err
                )

            return None

    async def async_fetch_live_snapshot_local(
        self, cam_id: str, jpeg_size: int | None = None
    ) -> bytes | None:
        """Fetch a live snapshot via LOCAL connection using HTTP Digest auth.

        For cameras like CAMERA_360 whose REMOTE snap.jpg returns 401,
        this opens a LOCAL connection to get Digest credentials and fetches
        snap.jpg directly from the camera's LAN IP.

        Uses auth_utils.async_digest_request (aiohttp) for non-blocking Digest auth.

        ``jpeg_size`` behaves as in async_fetch_live_snapshot: ``None`` keeps
        the full-resolution frame the persisting callers expect.
        """
        token = self.token
        if not token:
            return None
        # Same privacy short-circuit as the REMOTE fetch — the LAN snap.jpg
        # also returns 0 bytes when privacy mode is ON. shc_state_cache is
        # always initialized to {} in __init__, no getattr guard needed.
        if self.shc_state_cache.get(cam_id, {}).get("privacy_mode"):
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/connection"

        result = None
        try:
            # Reuse the pooled cloud session instead of opening a fresh
            # connector/TLS handshake on every LOCAL-bootstrap attempt
            # (Copilot review round 14).
            async with async_bosch_cloud_session_cm(self.hass) as session:
                async with asyncio.timeout(15):
                    async with session.put(
                        url,
                        json={
                            "type": "LOCAL",
                            "highQualityVideo": self.get_quality_params(cam_id)[0],
                        },
                        headers=headers,
                    ) as resp:
                        if resp.status not in (200, 201):
                            _LOGGER.debug(
                                "fetch_live_snapshot_local: PUT LOCAL → HTTP %d for %s",
                                resp.status,
                                cam_id,
                            )
                            return None
                        result = _json.loads(await resp.text())
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug(
                "fetch_live_snapshot_local: PUT error for %s: %s", cam_id, err
            )
            return None

        user = result.get("user")
        password = result.get("password")
        urls = result.get("urls", [])
        if not user or not password or not urls:
            _LOGGER.debug(
                "fetch_live_snapshot_local: missing credentials/urls for %s "
                "(has_user=%s, has_password=%s, urls=%d)",
                cam_id,
                bool(user),
                bool(password),
                len(urls),
            )
            return None

        camera_host = urls[0]  # e.g. "192.168.x.x:443"
        if not _is_safe_local_camera_host(camera_host):
            _LOGGER.warning(
                "Rejected unsafe/malformed LOCAL camera host for %s: %s",
                cam_id,
                camera_host[:60],
            )
            return None
        snap_url = (
            f"https://{camera_host}/snap.jpg?JpegSize={jpeg_size or JPEG_SIZE_FULL}"
        )

        # This is the only runtime path that ever receives freshly-issued
        # LOCAL Digest credentials — cache them so a cloud outage can fall
        # back to a LAN fetch using the last-known creds, and so
        # __init__.py's persistence layer has something to save across a
        # restart (bug-hunt 2026-07-27, Copilot review round 3).
        _host, _, _port_str = camera_host.partition(":")
        self.local_creds_cache[cam_id.upper()] = {
            "user": user,
            "password": password,
            "host": _host,
            "port": int(_port_str) if _port_str.isdigit() else 443,
            "ts": time.monotonic(),
        }

        session = async_get_clientsession(self.hass, verify_ssl=False)
        try:
            async with asyncio.timeout(12):
                async with await async_digest_request(
                    session,
                    "GET",
                    snap_url,
                    user,
                    password,
                    timeout=10.0,
                    ssl=False,
                ) as resp:
                    if resp.status == 200 and "image" in resp.headers.get(
                        "Content-Type", ""
                    ):
                        content: bytes = await resp.read()
                        _LOGGER.debug(
                            "fetch_live_snapshot_local: %s → %d bytes via Digest",
                            cam_id,
                            len(content),
                        )
                        return content
                    _LOGGER.debug(
                        "fetch_live_snapshot_local: Digest snap.jpg → HTTP %d for %s",
                        resp.status,
                        cam_id,
                    )
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            # ValueError: malformed/missing WWW-Authenticate (cam Digest state
            # may be half-rotated during FCM flap). Forum 998974/15 (Andrew75).
            _LOGGER.debug(
                "fetch_live_snapshot_local: aiohttp error for %s: %s", cam_id, err
            )
        return None

    # ── RCP protocol (Bosch Remote Configuration Protocol via cloud proxy) ──────
    def _invalidate_rcp_session(self, proxy_hash: str) -> None:
        """Drop a cached RCP session so the next call reopens the handshake.

        Call this when a downstream RCP read returns HTTP 401 (auth dropped),
        HTTP 403 (session expired), or RCP error 0x0c0d (session closed).
        Without invalidation the cache would keep serving the dead ID for
        its full 5-min TTL — readers would see None until the entry expired.
        """
        if self.rcp_session_cache.pop(proxy_hash, None) is not None:
            _LOGGER.debug("RCP session cache invalidated for %s", proxy_hash[:8])

    async def get_cached_rcp_session(
        self, proxy_host: str, proxy_hash: str
    ) -> str | None:
        """Return a cached RCP session ID, opening a new one if missing or expired.

        Caches valid session IDs for 5 minutes (TTL 300 s) to avoid the 2-step
        RCP handshake (0xff0c + 0xff0d) on every thumbnail or data fetch.

        Serialized per proxy_hash via `_get_rcp_session_lock` — Bosch's proxy
        only tolerates one live session per proxy_hash, so two callers racing
        an empty/expired cache would otherwise each open their own session and
        one gets rejected (sessionid 0x00000000).
        """
        async with self._get_rcp_session_lock(proxy_hash):
            now = time.monotonic()
            cached = self.rcp_session_cache.get(proxy_hash)
            if cached:
                session_id, expires_at = cached
                if now < expires_at:
                    return session_id
                del self.rcp_session_cache[proxy_hash]

            new_session_id: str | None = await self._rcp_session(proxy_host, proxy_hash)
            if new_session_id:
                self.rcp_session_cache[proxy_hash] = (
                    new_session_id,
                    now + 300.0,
                )  # 5-min TTL
            return new_session_id

    async def _rcp_session(self, proxy_host: str, proxy_hash: str) -> str | None:
        """Open an RCP session via the cloud proxy and return the sessionid, or None on failure.

        The RCP handshake consists of two steps:
          1. WRITE command 0xff0c with a fixed payload → extract <sessionid> from XML response
          2. WRITE command 0xff0d with the sessionid → ACK (confirms the session)

        Auth=3 (anonymous via URL hash) provides read-only access.
        The proxy_host should be in the form "proxy-NN.live.cbs.boschsecurity.com:42090".
        """
        base = f"https://{proxy_host}/{proxy_hash}/rcp.xml"
        init_payload = (
            "0x0102004000000000040000000000000000010000000000000001000000000000"
        )

        connector = aiohttp.TCPConnector(
            ssl=await async_get_bosch_cloud_ssl_context(self.hass)
        )
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                # Step 1: open session
                params1 = {
                    "command": "0xff0c",
                    "direction": "WRITE",
                    "type": "P_OCTET",
                    "payload": init_payload,
                }
                try:
                    async with asyncio.timeout(8):
                        async with session.get(base, params=params1) as resp:
                            if resp.status != 200:
                                _LOGGER.debug(
                                    "_rcp_session: step1 HTTP %d for %s",
                                    resp.status,
                                    proxy_host,
                                )
                                return None
                            text = await resp.text()
                except (TimeoutError, aiohttp.ClientError) as err:
                    _LOGGER.debug(
                        "_rcp_session: step1 error for %s: %s", proxy_host, err
                    )
                    return None

                # Parse <sessionid> from XML response
                m = _re.search(r"<sessionid>(\S+)</sessionid>", text, _re.IGNORECASE)
                if not m:
                    _LOGGER.debug(
                        "_rcp_session: no <sessionid> in response for %s: %s",
                        proxy_host,
                        text[:200],
                    )
                    return None
                session_id = m.group(1)

                # Step 2: ACK the session
                params2 = {
                    "command": "0xff0d",
                    "direction": "WRITE",
                    "type": "P_OCTET",
                    "sessionid": session_id,
                }
                try:
                    async with asyncio.timeout(8):
                        async with session.get(base, params=params2) as resp2:
                            _LOGGER.debug(
                                "_rcp_session: ACK HTTP %d for %s (sessionid=%s)",
                                resp2.status,
                                proxy_host,
                                session_id,
                            )
                except (TimeoutError, aiohttp.ClientError) as err:
                    _LOGGER.debug(
                        "_rcp_session: step2 error for %s: %s", proxy_host, err
                    )
                    # Session may still be valid — return it anyway

                return session_id
        finally:
            await connector.close()

    @staticmethod
    def _proxy_hash_from_rcp_base(rcp_base: str) -> str | None:
        """Extract proxy_hash from `https://host:port/{hash}/rcp.xml`."""
        parts = rcp_base.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-1] == "rcp.xml":
            return parts[-2]
        return None

    async def rcp_read(
        self,
        rcp_base: str,
        command: str,
        sessionid: str,
        type_: str = "P_OCTET",
        num: int = 0,
    ) -> bytes | None:
        """READ an RCP command and return the raw payload bytes, or None on failure.

        Uses the HA shared session to avoid creating a new
        connector+session per RCP command (prevents socket exhaustion).
        Invalidates the session cache on HTTP 401/403 or RCP <err>0x0c0d</err>
        (session closed) — the dead ID would otherwise block reads until TTL.
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session",
        # ...) working the same way it did before BoschCameraCoordinator
        # moved out of __init__.py — those patches target the package's own
        # namespace (kept local to avoid a module-level import cycle).
        params: dict[str, str] = {
            "command": command,
            "direction": "READ",
            "type": type_,
            "sessionid": sessionid,
        }
        if num:
            params["num"] = str(num)

        session = await async_get_bosch_cloud_session(self.hass)
        try:
            async with asyncio.timeout(8):
                async with session.get(rcp_base, params=params) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "rcp_read: command=%s HTTP %d", command, resp.status
                        )
                        if resp.status in (401, 403):
                            proxy_hash = self._proxy_hash_from_rcp_base(rcp_base)
                            if proxy_hash:
                                self._invalidate_rcp_session(proxy_hash)
                        return None
                    raw = await resp.read()
                    # RCP session-closed response: <err>0x0c0d</err>. Drop the
                    # cached session so the next read reopens the handshake.
                    if b"0x0c0d" in raw and b"<err>" in raw:
                        proxy_hash = self._proxy_hash_from_rcp_base(rcp_base)
                        if proxy_hash:
                            self._invalidate_rcp_session(proxy_hash)
                        return None
                    return bytes(raw)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("rcp_read: command=%s error: %s", command, err)
            return None

    async def _async_update_rcp_data(
        self, cam_id: str, proxy_host: str, proxy_hash: str
    ) -> None:
        """Fetch all RCP data for a camera via cloud proxy.

        Delegates to rcp.py's async_update_rcp_data() which reads:
          Phase 1: LED dimmer, privacy mask, clock, LAN IP, product name, bitrate
          Phase 2: alarm catalog, motion zones/coords, TLS cert, network services, IVA catalog
        """
        await async_update_rcp_data(self, cam_id, proxy_host, proxy_hash)

    def clock_offset(self, cam_id: str) -> float | None:
        """Return clock offset in seconds (camera time - server time), or None."""
        return self.rcp_clock_offset_cache.get(cam_id)

    def rcp_lan_ip(self, cam_id: str) -> str | None:
        """Return camera LAN IP from RCP 0x0a36, or None."""
        return self.rcp_lan_ip_cache.get(cam_id)

    def rcp_product_name(self, cam_id: str) -> str | None:
        """Return camera product name from RCP 0x0aea, or None."""
        return self.rcp_product_name_cache.get(cam_id)

    def rcp_bitrate_ladder(self, cam_id: str) -> list[int]:
        """Return bitrate ladder (kbps) from RCP 0x0c81, or empty list."""
        return self.rcp_bitrate_cache.get(cam_id, [])

    def get_quality(self, cam_id: str) -> str:
        """Return current quality preference: 'auto', 'high', or 'low'.

        Priority:
          1. Runtime override set by BoschVideoQualitySelect (session-only)
          2. 'auto' (LAN streams are always forced to hq=True, inst=1 regardless)
        """
        if cam_id in self._quality_preference:
            return self._quality_preference[cam_id]
        return "auto"

    def set_quality(self, cam_id: str, quality: str) -> None:
        """Set quality preference. quality must be 'auto', 'high', or 'low'."""
        self._quality_preference[cam_id] = quality
        # Invalidate proxy URL cache so next fetch uses a fresh PUT /connection
        # with the updated highQualityVideo flag
        self._proxy_url_cache.pop(cam_id, None)

    def get_quality_params(self, cam_id: str) -> tuple[bool, int]:
        """Return (highQualityVideo: bool, inst: int) for current quality preference."""
        q = self.get_quality(cam_id)
        if q == "high":
            return True, 1  # primary encoder, max quality (~30 Mbps)
        if q == "low":
            return False, 4  # low-bandwidth stream (~1.9 Mbps)
        return False, 2  # "auto" — iOS default, balanced (~7.5 Mbps)

    def motion_settings(self, cam_id: str) -> dict[str, Any]:
        """Return motion detection settings dict, or empty dict."""
        return self.data.get(cam_id, {}).get("motion", {})  # type: ignore[no-any-return]

    async def async_put_camera(
        self, cam_id: str, endpoint: str, payload: dict[str, Any] | None
    ) -> bool:
        """PUT to /v11/video_inputs/{cam_id}/{endpoint} with payload. Returns True on success.

        payload=None sends a truly empty body (no bytes, not even "{}") —
        required for soft_reset/hard_reset. Verified from the decompiled
        Bosch app (research/apk_2.12.0): UpdateSoftReset/UpdateHardReset
        call the 2-arg PutStringAsync(url, accessToken) overload, whose
        argsAsJson parameter defaults to "" — StringContent("", ...,
        "application/json") is Content-Length: 0, not the 2-byte "{}"
        aiohttp's `json={}` would send. Every other endpoint this method
        is used for sends a real payload dict, so this only changes
        behavior for the two reset endpoints.
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session",
        # ...) working the same way it did before BoschCameraCoordinator
        # moved out of __init__.py — those patches target the package's own
        # namespace (kept local to avoid a module-level import cycle).
        token = self.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        put_kwargs: dict[str, Any] = (
            {"data": ""} if payload is None else {"json": payload}
        )
        session = await async_get_bosch_cloud_session(self.hass)
        url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/{endpoint}"
        try:
            async with asyncio.timeout(10):
                async with session.put(url, headers=headers, **put_kwargs) as resp:
                    if resp.status == 401:
                        # Token expired — refresh and retry once
                        _LOGGER.info(
                            "Camera write %s/%s got 401 — refreshing token",
                            cam_id,
                            endpoint,
                        )
                        try:
                            token = await self.ensure_valid_token(token)
                            headers["Authorization"] = f"Bearer {token}"
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:  # noqa: BLE001 — ensure_valid_token can raise ConfigEntryAuthFailed/UpdateFailed/RefreshTokenInvalidError/AuthServerOutageError/aiohttp errors; any failure here must just fail this one write, not propagate
                            _LOGGER.debug(
                                "async_put_camera token refresh failed: %s", err
                            )
                            return False
                        async with asyncio.timeout(10):
                            async with session.put(
                                url, headers=headers, **put_kwargs
                            ) as resp2:
                                # Must accept the same status set as the
                                # initial attempt below (200/201/204) — this
                                # is the identical write, retried after a
                                # token refresh, not a different semantic
                                # operation (Copilot review round 9).
                                ok2 = resp2.status in (200, 201, 204)
                                if not ok2:
                                    body2 = await resp2.text()
                                    _LOGGER.debug(
                                        "async_put_camera %s/%s: retry HTTP %d — %s",
                                        cam_id,
                                        endpoint,
                                        resp2.status,
                                        body2[:200],
                                    )
                                return ok2
                    ok = resp.status in (200, 201, 204)
                    if not ok:
                        body = await resp.text()
                        _LOGGER.debug(
                            "async_put_camera %s/%s: HTTP %d — %s",
                            cam_id,
                            endpoint,
                            resp.status,
                            body[:200],
                        )
                    return ok
        except (aiohttp.ClientError, TimeoutError, UnicodeDecodeError) as err:
            _LOGGER.warning("Camera write %s/%s error: %s", cam_id, endpoint, err)
            return False

    # SMB/NAS upload, download, cleanup, and disk-check functions are in smb.py
