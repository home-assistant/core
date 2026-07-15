"""Bosch Smart Home Camera — Home Assistant Custom Integration.

Provides camera, sensor and button entities for all Bosch Smart Home cameras
via the Bosch Cloud API (residential.cbs.boschsecurity.com).

Features (all toggleable in Options):
  • Camera snapshot entities  — latest motion-triggered JPEG per camera
  • Status + event sensors    — ONLINE/OFFLINE, last event timestamp, events-today count
  • Snapshot trigger buttons  — force immediate refresh; "Open Live Stream" button
  • Auto-download             — background download of all event files to a local folder
  • Live stream               — full 30fps H.264 1920×1080 + AAC audio via rtsps://:443
                                 ConnectionType "REMOTE" → proxy-NN:443/{hash}/rtsp_tunnel

Installation:
  1. Copy bosch_shc_camera/ to /config/custom_components/
  2. Restart Home Assistant
  3. Settings → Integrations → Add → "Bosch Smart Home Camera"
  4. Enter Bearer token

No user data is hardcoded. All configuration via the HA UI.
"""

import asyncio
import logging
import re as _re_mod
import time
from typing import Any, override

import aiohttp
from bosch_shc_camera_client.auth_utils import (
    async_digest_request as async_digest_request,  # re-export: mypy --no-implicit-reexport (coordinator.py imports it via `from . import`)
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession as async_get_clientsession,  # re-export: mypy --no-implicit-reexport (coordinator.py imports it via `from . import`)
)
from homeassistant.helpers.storage import Store

from . import recorder as nvr_recorder
from .cloud_ssl import (
    async_get_bosch_cloud_session as async_get_bosch_cloud_session,  # re-export: mypy --no-implicit-reexport (services.py/live_connection.py/token_auth.py import it via `from . import`)
)
from .coordinator import (
    BoschCameraConfigEntry as BoschCameraConfigEntry,  # re-export: mypy --no-implicit-reexport (platform modules import it via `from . import`)
    BoschCameraCoordinator as BoschCameraCoordinator,  # re-export: mypy --no-implicit-reexport (platform modules import it via `from . import`)
    _is_safe_bosch_url as _is_safe_bosch_url,  # re-export: mypy --no-implicit-reexport (camera.py imports it via `from . import`)
    get_options as get_options,  # re-export: mypy --no-implicit-reexport (button.py/image.py/sensor.py/switch.py import it via `from . import`)
)
from .services import _register_services
from .tls_proxy import (
    pre_warm_rtsp as pre_warm_rtsp,  # re-export: mypy --no-implicit-reexport (live_connection.py imports it via `from . import`)
    stop_all_proxies,
)

_LOGGER = logging.getLogger(__name__)

# FCM_DELIVERY_DEAD_AFTER_SEC moved to const.py — shared with event_dispatch.py.

# SLOW_TIER_MAX_DEFER_SEC moved to const.py — shared with slow_tier.py.

# _FRESH_SNAP_TTL / FCM_DOWN_EVENT_POLL_SEC / CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC
# moved to coordinator.py — only used by BoschCameraCoordinator.

# Module-level debounce dict for auto-describe-on-motion — keyed by cam_id.
# Must live at module level (not inside async_setup_entry) so it survives
# integration reloads: re-entering async_setup_entry would otherwise reset
# the dict and allow a burst of back-to-back AI calls across the reload gap.
_AI_MOTION_DEBOUNCE: dict[str, float] = {}
_AI_MOTION_DEBOUNCE_SEC = 30.0

# Read integration version once at import time (sync I/O at module level is fine — import
# happens in the executor during HA startup, not inside the event loop).
try:
    import json as _json
    import pathlib as _pathlib

    _INTEGRATION_VERSION: str = _json.loads(
        (_pathlib.Path(__file__).parent / "manifest.json").read_text()
    )["version"]
except Exception:  # pragma: no cover — manifest.json ships with the package; only fires on a corrupted install
    _INTEGRATION_VERSION = "unknown"


class _StreamSupportNoiseFilter(logging.Filter):
    """Rate-limit HA camera-component log spam during stream pre-warm.

    Handles two recurring burst patterns from HA's camera component:

    1. "does not support play stream service" — fired when stream_source()
       returns None during LOCAL pre-warm (~25 s window). Multiple tabs /
       Companion app / card HLS fallback can produce 9 of these in 15 s.
       Rate-limited to 1 per 30 s *per entity_id* (bosch_* only).

    2. "Camera not found" — fired when the browser requests WebRTC for a
       camera not yet registered in go2rtc (startup race: browser reconnects
       and sees cached "streaming" state before the coordinator has finished
       re-registering the stream). Rate-limited to 1 per 60 s globally
       (message carries no entity_id so per-entity tracking isn't possible).

    A real "stream truly broken" issue still surfaces because one ERROR per
    window is always passed through. Other camera integrations are unaffected.
    """

    _MAX_TRACKED = 32  # max entity IDs to track — prevents unbounded growth
    _NOT_FOUND_KEY = "__camera_not_found__"
    _NOT_FOUND_WINDOW = 60.0

    def __init__(self) -> None:
        super().__init__()
        self._last_passed: dict[str, float] = {}

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)

        # ── "Camera not found" burst (startup race, no entity_id in message) ──
        if "Camera not found" in msg and "Error requesting stream" in msg:
            import time as _t

            now = _t.monotonic()
            last = self._last_passed.get(self._NOT_FOUND_KEY, float("-inf"))
            if (now - last) < self._NOT_FOUND_WINDOW:
                return False
            self._last_passed[self._NOT_FOUND_KEY] = now
            return True

        # ── "does not support play stream service" burst (pre-warm window) ──
        if "does not support play stream service" not in msg:
            return True
        # Extract entity_id from "Error requesting stream: camera.<id> ..."
        ent = ""
        prefix = "camera."
        idx = msg.find(prefix)
        if idx != -1:
            tail = msg[idx + len(prefix) :]
            ent = tail.split(" ", 1)[0]
        if not ent.startswith("bosch_"):
            return True  # not us, leave alone
        import time as _t

        now = _t.monotonic()
        last = self._last_passed.get(ent, float("-inf"))
        if (now - last) < 30.0:
            return False
        # Prune oldest entry when dict grows too large
        if len(self._last_passed) >= self._MAX_TRACKED:
            oldest = min(self._last_passed, key=self._last_passed.__getitem__)
            del self._last_passed[oldest]
        self._last_passed[ent] = now
        return True


def _install_stream_support_noise_filter() -> None:
    """Install the Bosch-side filter on HA's camera component logger once."""
    cam_logger = logging.getLogger("homeassistant.components.camera")
    for f in cam_logger.filters:
        if isinstance(f, _StreamSupportNoiseFilter):
            return
    cam_logger.addFilter(_StreamSupportNoiseFilter())


class _StreamWorkerErrorListener(logging.Handler):
    """Intercept `Error from stream worker` log records from HA's stream component.

    Routes each one to the coordinator's stream-error handler.

    HA's stream component runs an auto-restart loop on worker crashes
    (`stream.__init__.Stream._run_worker`): worker fails → `_set_state(False)`
    (yellow in the card) → backoff wait → `_set_state(True)` (briefly blue) →
    retry. This produces a continuous yellow→blue→yellow cycle that our own
    polling watchdog misses when its 60 s tick happens to land during a brief
    "available" window. Instead of polling, we listen to HA's own error log:
    every "Error from stream worker" on a logger named
    `homeassistant.components.stream.stream.camera.<entity_id>` increments the
    coordinator's per-camera counter, and once the threshold is reached the
    coordinator forces REMOTE on the next `try_live_connection` — escaping
    the cycle deterministically on N consecutive stream-worker errors rather
    than hoping the 60 s tick catches a failing state.
    """

    def __init__(self, coordinator: BoschCameraCoordinator) -> None:
        super().__init__(logging.ERROR)
        self._coordinator: BoschCameraCoordinator | None = coordinator

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self._coordinator is None:
                return
            if record.levelno < logging.ERROR:
                return
            # Only interested in HA's stream worker errors. Other errors on
            # the same parent logger (e.g. RecorderBuildError, HLS output
            # failures) aren't our concern.
            msg = record.getMessage()
            if "Error from stream worker" not in msg:
                return
            # Logger name shape:
            # homeassistant.components.stream.stream.camera.bosch_<slug>
            name = record.name
            marker = ".stream.camera."
            if marker not in name:
                return
            entity_id = "camera." + name.rsplit(marker, 1)[1]
            # Resolve cam_id from entity_id via the coordinator's entity map.
            # `emit` runs in the logging thread — defer the async work.
            cam_id = None
            for cid, entity in self._coordinator.camera_entities.items():
                if getattr(entity, "entity_id", None) == entity_id:
                    cam_id = cid
                    break
            if not cam_id:
                return
            loop = self._coordinator.hass.loop
            loop.call_soon_threadsafe(
                self._coordinator.schedule_stream_worker_error, cam_id, msg
            )
        except Exception:  # logging.emit handler must never raise; exception would recurse into logging itself
            # Never let the log handler crash the event loop or the logger.
            # Intentionally broad: this runs inside logging.emit and any
            # exception here would be routed back to logging's own error path.
            pass


def _looks_like_uuid_name(n: str) -> bool:
    """True if `n` looks like a `Bosch <UUID>` placeholder name.

    Detects names a previous cloud-degraded startup leaked into the device
    registry when `coordinator.data[cam_id].info.title` was empty and the
    code fell back to using the cam_id (UUID-style) as the title.
    """
    return len(n) >= 36 and n.upper().count("-") >= 4


def _rehydrate_cams_from_registry(
    hass: HomeAssistant,
    entry_id: str,
) -> tuple[set[str], dict[str, str]]:
    """Discover known cam_ids + human-readable titles from the HA registries.

    Used by `async_setup_entry` when the first cloud refresh raises
    `ConfigEntryNotReady` — without this rehydration, no entities would
    materialise on a cold start during a cloud outage, even though privacy
    / light / LAN-ping all work without the cloud.

    Returns `(cam_ids, cam_titles)`. `cam_titles` is keyed by cam_id.
    Title-resolution order:
      1. `device.name_by_user` — manual rename always wins.
      2. `device.name` if it is NOT a `Bosch <UUID>` placeholder (which we
         repair on the way out).
      3. derived from the camera entity_id slug (`camera.bosch_terrasse` →
         `Terrasse`).
      4. fall back to the cam_id itself.

    If a stale `Bosch <UUID>` placeholder is detected in the device
    registry, the device name is repaired in place so newly-registered
    entities pick up the correct slug.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    ereg = er.async_get(hass)
    dreg = dr.async_get(hass)
    cam_ids: set[str] = set()
    for ent in er.async_entries_for_config_entry(ereg, entry_id):
        # Unique IDs in this integration consistently embed the UUID-style
        # cam_id; the first match yields the canonical set.
        for part in ent.unique_id.split("_"):
            if len(part) == 36 and part.count("-") == 4:
                cam_ids.add(part.upper())
                break
    cam_titles: dict[str, str] = {}
    for cid in cam_ids:
        device = dreg.async_get_device(identifiers={(DOMAIN, cid)})
        title: str | None = None
        if device and device.name_by_user:
            t = device.name_by_user
            title = t.removeprefix("Bosch ")
        elif device and device.name and not _looks_like_uuid_name(device.name):
            t = device.name
            title = t.removeprefix("Bosch ")
        else:
            cam_eid = ereg.async_get_entity_id(
                "camera",
                DOMAIN,
                f"bosch_shc_cam_{cid.lower()}",
            )
            if cam_eid and cam_eid.startswith("camera.bosch_"):
                slug = cam_eid[len("camera.bosch_") :]
                title = slug.replace("_", " ").title()
        if title:
            cam_titles[cid] = title
            # Repair the device name in the registry if it was a broken
            # `Bosch <UUID>` placeholder from a prior degraded startup.
            # Sticky-name damage compounds across restarts otherwise.
            if device and device.name and _looks_like_uuid_name(device.name):
                dreg.async_update_device(device.id, name=f"Bosch {title}")
                _LOGGER.info(
                    "Repaired device name for %s: 'Bosch %s' (was a UUID placeholder)",
                    cid[:8],
                    title,
                )
    return cam_ids, cam_titles


def _redact_creds(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a dict with the `password` field redacted for safe logging.

    The camera-issued Digest password is ephemeral (rotates on camera reboot)
    but still a credential — replacing it with a short prefix + length keeps
    the log line useful for diagnostics without exposing the secret.
    """
    return {
        k: (
            f"{v[:3]}***({len(v)} chars)"
            if k == "password" and isinstance(v, str)
            else v
        )
        for k, v in d.items()
    }


from .const import (
    ALL_PLATFORMS,
    CLOUD_API as CLOUD_API,  # re-export: mypy --no-implicit-reexport (services.py imports it via `from . import`)
    DEFAULT_OPTIONS as DEFAULT_OPTIONS,  # re-export: mypy --no-implicit-reexport (config_flow.py imports it via `from . import`)
    DOMAIN,
    LIVE_SESSION_TTL,  # re-exported for tests
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# hass.data key holding the per-entry options snapshot used by
# _async_options_updated to tell a real options edit apart from the frequent
# data-only writes (token refresh, FCM token/credential persistence). Kept in
# hass.data (not only on the coordinator) so the comparison survives the brief
# `entry.runtime_data is None` window during a reload — see _async_options_updated.
OPTIONS_SNAPSHOT_KEY = f"{DOMAIN}_options_snapshot"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Bosch Smart Home Camera integration (domain-level)."""
    # Register services at domain level — ensures they are available even when
    # the config entry is in setup_retry (e.g. token expired).
    # Without this, the Lovelace card shows "action not found" errors.
    _register_services(hass)

    # Auto-import Bosch's fixed public OAuth2 client (identical in every
    # Android APK, not a per-user secret) as the default application
    # credential, so a fresh setup needs zero manual Settings →
    # Application Credentials step — same pattern as overkiz/vicare/
    # ondilo_ico. See application_credentials.py's module docstring for the
    # full rationale. Idempotent (async_import_client_credential no-ops if
    # already imported), so safe to call on every async_setup (e.g. reload).
    # Local import (not top-level): CLIENT_ID/CLIENT_SECRET live in
    # config_flow.py, which itself imports DEFAULT_OPTIONS/DOMAIN from this
    # module — a top-level import here would be circular at module load time.
    from .config_flow import CLIENT_ID, CLIENT_SECRET

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Bosch SingleKey ID"),
    )

    # Serve the bundled card JS files via HA's static path handler.
    # cache_headers=False → no-store so browsers always revalidate.
    from pathlib import Path as _Path

    from homeassistant.components.http import StaticPathConfig as _StaticPathConfig
    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

    from .const import CARD_VERSION

    _www = _Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [
            _StaticPathConfig(
                f"/{DOMAIN}/bosch-camera-card.js",
                str(_www / "bosch-camera-card.js"),
                False,
            ),
            _StaticPathConfig(
                f"/{DOMAIN}/bosch-camera-autoplay-fix.js",
                str(_www / "bosch-camera-autoplay-fix.js"),
                False,
            ),
        ]
    )

    async def _register_lovelace_resources() -> None:
        """Write card URLs into Lovelace resource storage (appears in UI)."""
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning(
                "%s: Lovelace not available — card not auto-registered", DOMAIN
            )
            return
        resources = lovelace.resources
        await resources.async_load()

        # Remove legacy /local/ entries left over from pre-v10.3.19 installs.
        # Having both old and new entries causes the card to load twice, which
        # triggers a "custom element already defined" error and the older cached
        # version wins.
        # Also remove the bosch-camera-autoplay-fix.js resource (ANY path):
        # deprecated as of v13.3.0 — the watchdog it contained is a no-op now
        # (the card self-heals per-instance), and its old index-paired HLS
        # injection could disrupt the wrong camera. We stop registering it
        # (loop below) and delete any previously auto-registered entry here. The
        # static path still serves the no-op stub, so cached/manual references
        # resolve harmlessly instead of 404-ing.
        _remove_prefixes = (
            "/local/bosch-camera-card",
            "/local/bosch-camera-autoplay-fix",
            f"/{DOMAIN}/bosch-camera-autoplay-fix",
        )
        for item in list(resources.async_items()):
            if item.get("url", "").startswith(_remove_prefixes):
                await resources.async_delete_item(item["id"])
                _LOGGER.debug(
                    "%s: Removed deprecated Lovelace resource: %s", DOMAIN, item["url"]
                )

        for card_path in (f"/{DOMAIN}/bosch-camera-card.js",):
            versioned = f"{card_path}?v={CARD_VERSION}"
            existing_id = None
            already_current = False
            for item in resources.async_items():
                item_url = item.get("url", "")
                if item_url.startswith(card_path):
                    already_current = item_url == versioned
                    existing_id = item["id"]
                    break
            if already_current:
                _LOGGER.debug(
                    "%s: Lovelace resource already current: %s", DOMAIN, versioned
                )
                continue
            if existing_id:
                await resources.async_update_item(
                    existing_id, {"res_type": "module", "url": versioned}
                )
                _LOGGER.debug("%s: Updated Lovelace resource: %s", DOMAIN, versioned)
            else:
                await resources.async_create_item(
                    {"res_type": "module", "url": versioned}
                )
                _LOGGER.debug("%s: Registered Lovelace resource: %s", DOMAIN, versioned)

    if hass.is_running:
        # Integration reloaded while HA is already up
        await _register_lovelace_resources()
    else:
        from homeassistant.core import Event as _Event, callback as _callback

        @_callback
        def _on_ha_started(_event: _Event) -> None:
            hass.async_create_task(_register_lovelace_resources())

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)

    return True


# Regex for the v11.0.0 doubled-prefix bug. A buggy entity_id looks like
# `button.bosch_est_bosch_est_refresh_snapshot`: domain, dot, two identical
# `bosch_<slug>_` runs, then the suffix. The backreference `\2` makes the
# match require the slug to literally repeat, so single-prefix entities
# (e.g. `switch.bosch_est_live_stream`) are never touched.
_DOUBLED_PREFIX_RE = _re_mod.compile(
    r"^(button|number|select|update|binary_sensor|light)"
    r"\.bosch_([a-z0-9_]+?)_bosch_\2_(.+)$"
)


async def _migrate_doubled_prefix_entity_ids(
    hass: HomeAssistant, config_entry_id: str
) -> int:
    """Rename entity_ids carrying the v11.0.0 doubled-prefix bug.

    v11.0.0 Gold-Compliance migration added `_attr_has_entity_name = True`
    to 30+ entity classes without removing the device-name prefix from
    their `_attr_name`, so HA prepended the device name a second time and
    the buggy entity_id stuck in the registry. v12.3.0 fixes the source;
    this helper renames the surviving entries so they match what the
    corrected code now produces.

    Reported in forum 998974/15 (Andrew75, 2026-05-15).
    """
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)
    renamed: list[tuple[str, str]] = []

    def _cb(reg_entry: er.RegistryEntry) -> dict[str, Any] | None:
        m = _DOUBLED_PREFIX_RE.match(reg_entry.entity_id)
        if not m:
            return None
        domain_part, slug, rest = m.group(1), m.group(2), m.group(3)
        new_eid = f"{domain_part}.bosch_{slug}_{rest}"
        # Skip if the new entity_id is already taken — avoid the ValueError
        # async_update_entity would raise. Shouldn't happen in practice (the
        # old entity owned the unique_id), but guard anyway.
        if ent_reg.async_get(new_eid):
            return None
        renamed.append((reg_entry.entity_id, new_eid))
        return {"new_entity_id": new_eid}

    await er.async_migrate_entries(hass, config_entry_id, _cb)

    if renamed:
        _LOGGER.warning(
            "Migrated %d entity_id(s) with the v11.0.0 doubled-prefix bug. "
            "Update automations/scripts/Lovelace dashboards that reference: %s",
            len(renamed),
            "; ".join(f"{old} → {new}" for old, new in renamed),
        )
        examples = ", ".join(f"`{old}` → `{new}`" for old, new in renamed[:5])
        if len(renamed) > 5:
            examples += ", …"
        ir.async_create_issue(
            hass,
            DOMAIN,
            "doubled_prefix_entity_ids_migrated",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="doubled_prefix_entity_ids_migrated",
            translation_placeholders={
                "count": str(len(renamed)),
                "examples": examples,
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "doubled_prefix_entity_ids_migrated")

    return len(renamed)


async def async_migrate_entry(
    hass: HomeAssistant, entry: BoschCameraConfigEntry
) -> bool:
    """Migrate config entries to the current schema version.

    v1 → v2 (2026-05-17, v12.4.3): DEFAULT_OPTIONS['stream_connection_type']
    flipped from 'auto' to 'local'. Entries that never explicitly set the
    option silently relied on the auto default; without this migration they
    would switch to local-only on first start after upgrade and lose their
    REMOTE-fallback safety net. Persist 'auto' explicitly so existing
    installs keep their current behaviour. New installs (created after the
    bump) get 'local' via DEFAULT_OPTIONS.

    v2 → v3 (2026-05-18, v12.4.5): fcm_push_mode is now binary — 'auto' (use
    OSS FCM key with automatic polling fallback) or 'polling' (skip FCM
    entirely). Legacy 'ios' / 'android' values from earlier versions get
    coerced to 'auto'; the OSS-sanctioned Android Firebase app handles both
    platforms transparently.

    Additionally, when the mode is FCM-bound ('ios', 'android', or the legacy
    'auto' which used an iOS-first chain), fcm_credentials and
    fcm_registered_token are cleared from entry.data so that
    register_fcm_with_bosch detects a missing token and forces re-registration
    with deviceType=ANDROID against Bosch CBS. Without this clearance,
    register_fcm_with_bosch sees "token unchanged" and skips re-registration,
    leaving Bosch CBS with deviceType=IOS while the HA client registers
    platform=ANDROID at Firebase — silently breaking push routing for every
    upgrader on a legacy FCM mode.

    Version steps accumulate into shared `new_options`/`new_data` dicts and
    are persisted with a SINGLE `async_update_entry` call at the end (Runde 2
    P2 #6) — a v1 entry migrating straight to v3 previously triggered TWO
    separate update calls (one per version step), each firing its own
    reload/event cycle. The log message for each logical step still fires
    independently so the migration history stays visible in the log.
    """
    starting_version = entry.version
    new_options = dict(entry.options)
    new_data = dict(entry.data)
    final_version = starting_version

    if starting_version < 2:
        if "stream_connection_type" not in new_options:
            new_options["stream_connection_type"] = "auto"
            _LOGGER.info(
                "Migration v1→v2: preserved stream_connection_type=auto for entry %s",
                entry.entry_id,
            )
        final_version = 2
    if starting_version < 3:
        fcm_mode = new_options.get("fcm_push_mode")
        if fcm_mode in ("ios", "android"):
            new_options["fcm_push_mode"] = "auto"
        if fcm_mode in ("ios", "android", "auto"):
            # Clear stale FCM registration so register_fcm_with_bosch forces
            # re-registration with deviceType=ANDROID on next startup.
            # 'auto' in v2 used an iOS-first Bosch registration path; that token
            # is equally stale after switching to the OSS Android Firebase key.
            new_data.pop("fcm_credentials", None)
            new_data.pop("fcm_registered_token", None)
            _LOGGER.info(
                "Migration v2→v3: rewrote fcm_push_mode to 'auto' + cleared FCM "
                "creds + token for re-registration with deviceType=ANDROID for "
                "entry %s",
                entry.entry_id,
            )
        final_version = 3

    if final_version != starting_version:
        hass.config_entries.async_update_entry(
            entry, options=new_options, data=new_data, version=final_version
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BoschCameraConfigEntry) -> bool:
    """Set up Bosch Smart Home Camera from a config entry."""
    coordinator = BoschCameraCoordinator(hass, entry)

    # Post-update feedback prompt — one-time per integration version. When the
    # user updates to a new version we file a persistent notification pointing
    # to GitHub Discussions so feedback channels are discoverable from the HA
    # UI itself, not buried in the README. Stored per-version in entry.options;
    # we only fire when the persisted "feedback_hint_version" != current.
    # Multi-lang: picks message text per `hass.config.language`; falls back to
    # English when the language isn't in the small inline dict below (we keep
    # this inline rather than in translations/ because persistent_notification
    # doesn't go through the entity-translation pipeline).
    try:
        last_hint_version = entry.options.get("feedback_hint_version", "")
        if _INTEGRATION_VERSION not in (last_hint_version, "unknown"):
            _disc_url = "https://github.com/mosandlt/Bosch-Smart-Home-Camera-Tool-HomeAssistant/discussions"
            _iss_url = "https://github.com/mosandlt/Bosch-Smart-Home-Camera-Tool-HomeAssistant/issues"
            _lang_messages: dict[str, tuple[str, str]] = {
                "de": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Update auf **v{_INTEGRATION_VERSION}** abgeschlossen. "
                    f"Feedback, Fragen, Ideen? Nutze die neuen "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Bug-Reports weiter via [Issues]({_iss_url}).",
                ),
                "en": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Updated to **v{_INTEGRATION_VERSION}**. "
                    f"Feedback, questions, ideas? Use the new "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Bug reports still on [Issues]({_iss_url}).",
                ),
                "fr": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Mise à jour vers **v{_INTEGRATION_VERSION}** terminée. "
                    f"Commentaires, questions, idées ? Utilisez les nouvelles "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Rapports de bugs toujours via [Issues]({_iss_url}).",
                ),
                "es": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Actualización a **v{_INTEGRATION_VERSION}** completada. "
                    f"¿Comentarios, preguntas, ideas? Usa las nuevas "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Informes de errores siguen en [Issues]({_iss_url}).",
                ),
                "it": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Aggiornamento a **v{_INTEGRATION_VERSION}** completato. "
                    f"Feedback, domande, idee? Usa le nuove "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Segnalazioni di bug ancora su [Issues]({_iss_url}).",
                ),
                "nl": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Bijgewerkt naar **v{_INTEGRATION_VERSION}**. "
                    f"Feedback, vragen, ideeën? Gebruik de nieuwe "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Bugmeldingen nog steeds via [Issues]({_iss_url}).",
                ),
                "pl": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Aktualizacja do **v{_INTEGRATION_VERSION}** zakończona. "
                    f"Opinie, pytania, pomysły? Skorzystaj z nowych "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Zgłoszenia błędów nadal przez [Issues]({_iss_url}).",
                ),
                "pt": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Atualização para **v{_INTEGRATION_VERSION}** concluída. "
                    f"Feedback, perguntas, ideias? Use as novas "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Relatórios de bugs ainda via [Issues]({_iss_url}).",
                ),
                "ru": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Обновление до **v{_INTEGRATION_VERSION}** завершено. "
                    f"Отзывы, вопросы, идеи? Используйте новые "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Сообщения об ошибках по-прежнему в [Issues]({_iss_url}).",
                ),
                "uk": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"Оновлення до **v{_INTEGRATION_VERSION}** завершено. "
                    f"Відгуки, питання, ідеї? Використовуйте нові "
                    f"[GitHub Discussions]({_disc_url}). "
                    f"Звіти про помилки досі через [Issues]({_iss_url}).",
                ),
                "zh-Hans": (
                    f"Bosch Smart Home Camera v{_INTEGRATION_VERSION}",
                    f"已更新至 **v{_INTEGRATION_VERSION}**。"
                    f"反馈、问题、建议？请使用新的 "
                    f"[GitHub Discussions]({_disc_url})。"
                    f"错误报告请继续通过 [Issues]({_iss_url}) 提交。",
                ),
            }
            _lang_raw = (hass.config.language or "en").lower()
            # zh-CN / zh-Hans normalisation
            if _lang_raw.startswith("zh"):
                _lang_key = "zh-Hans"
            else:
                _lang_key = _lang_raw.split("-", 1)[0]
            _title, _message = _lang_messages.get(_lang_key, _lang_messages["en"])
            hass.async_create_task(
                hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "notification_id": f"{DOMAIN}_feedback_v{_INTEGRATION_VERSION}",
                        "title": _title,
                        "message": _message,
                    },
                    blocking=False,
                )
            )
            # Persist version so the prompt won't fire again until next update
            new_opts = dict(entry.options)
            new_opts["feedback_hint_version"] = _INTEGRATION_VERSION
            hass.config_entries.async_update_entry(entry, options=new_opts)
    except Exception as _fb_err:
        _LOGGER.debug("feedback-hint suppressed: %s", _fb_err)

    # Load the persistent maintenance-notification dedup key so a restart
    # mid-window does not re-fire the "Wartung läuft" alert. Stored as
    # `[link, state]`. Bug 2026-05-20: Thomas received the same active-
    # maintenance announcement ~20 times because every HA restart wiped
    # `_maintenance_notified_key` and the next coordinator tick re-fired
    # the active-state notify.
    _maint_key_store: Store[dict[str, str]] = Store(
        hass, version=1, key=f"{DOMAIN}_maint_notified"
    )
    coordinator.maint_notified_store = _maint_key_store
    _persisted_maint_key = await _maint_key_store.async_load() or None
    if isinstance(_persisted_maint_key, dict):
        _link = _persisted_maint_key.get("link")
        _state = _persisted_maint_key.get("state")
        if isinstance(_link, str) and isinstance(_state, str):
            coordinator.maintenance_notified_key = (_link, _state)
            _LOGGER.info(
                "Loaded persisted maintenance-notify dedup key: %s for %s",
                _state,
                _link[:60],
            )

    # Same problem for cloud-state-alert: `_cloud_outage_notified` lived only
    # in memory, so a restart during an outage could re-fire "Cloud nicht
    # erreichbar". Persist a tiny boolean so restarts honour the dedup.
    _cloud_alert_store: Store = Store(
        hass, version=1, key=f"{DOMAIN}_cloud_alert_state"
    )
    coordinator.cloud_alert_store = _cloud_alert_store
    _persisted_cloud_alert = await _cloud_alert_store.async_load() or {}
    if isinstance(_persisted_cloud_alert, dict):
        if _persisted_cloud_alert.get("outage_notified") is True:
            coordinator.cloud_outage_notified = True
            _LOGGER.info(
                "Loaded persisted cloud-outage-notified flag (was True at last save)",
            )

    # Load the persistent LAN-IP map (cam_id → IP) so the LAN-ping helpers
    # have something to work with on a cloud-degraded startup. Written below
    # on every successful coordinator refresh.
    _lan_ips_store: Store = Store(hass, version=1, key=f"{DOMAIN}_lan_ips")
    coordinator.lan_ips_store = _lan_ips_store
    _persisted_ips = await _lan_ips_store.async_load() or {}
    if isinstance(_persisted_ips, dict):
        for _cid, _ip in _persisted_ips.items():
            if isinstance(_cid, str) and isinstance(_ip, str):
                coordinator.rcp_lan_ip_cache[_cid.upper()] = _ip
        if _persisted_ips:
            _LOGGER.info(
                "Loaded %d persisted LAN IP(s) for cloud-degraded LAN ping",
                len(_persisted_ips),
            )

    # Load the persistent hardware-version map (cam_id → hw_version). Without
    # this, a cold start during a Bosch cloud 5xx leaves `_hw_version` empty
    # and `_is_gen2()` returns False for every camera — which in turn makes
    # the privacy / front-light switches unavailable even though the LAN
    # RCP path would work. v12.4.10 added the LAN-fallback availability gate
    # but missed this persistence; 2026-05-20 maintenance window exposed the
    # gap (cloud 503 for 30+ minutes, switches grey, no toggle).
    _hw_version_store: Store = Store(hass, version=1, key=f"{DOMAIN}_hw_versions")
    coordinator.hw_version_store = _hw_version_store
    _persisted_hw = await _hw_version_store.async_load() or {}
    if isinstance(_persisted_hw, dict):
        for _cid, _hw in _persisted_hw.items():
            if isinstance(_cid, str) and isinstance(_hw, str):
                coordinator.hw_version[_cid.upper()] = _hw
        if _persisted_hw:
            _LOGGER.info(
                "Loaded %d persisted hardware version(s) for cloud-degraded LAN fallback",
                len(_persisted_hw),
            )

    # Load persisted LOCAL Digest creds (cam_id → {user, password, host, port}).
    # Bosch cycles these creds on every PUT /connection LOCAL — typically valid
    # for the lifetime of a session, occasionally beyond. Persisting lets the
    # LAN-fallback privacy / light writes work across HA restarts during a
    # multi-hour cloud outage; without this the in-memory cache is empty on
    # cold start and every RCP write returns <err> from the camera.
    # Security note: stored in HA's .storage (same protection level as the
    # cloud bearer token). LAN-only effective scope (camera not internet-exposed).
    _creds_store: Store = Store(hass, version=1, key=f"{DOMAIN}_local_creds")
    coordinator.local_creds_store = _creds_store
    _persisted_creds = await _creds_store.async_load() or {}
    if isinstance(_persisted_creds, dict):
        _loaded_creds = 0
        for _cid, _payload in _persisted_creds.items():
            if not (isinstance(_cid, str) and isinstance(_payload, dict)):
                continue
            if "user" in _payload and "password" in _payload and "host" in _payload:
                coordinator.local_creds_cache[_cid.upper()] = {
                    "user": _payload["user"],
                    "password": _payload["password"],
                    "host": _payload["host"],
                    "port": int(_payload.get("port", 443)),
                    "ts": time.monotonic(),
                }
                _loaded_creds += 1
        if _loaded_creds:
            _LOGGER.info(
                "Loaded %d persisted LOCAL Digest cred(s) for LAN-fallback writes",
                _loaded_creds,
            )

    # Belt-and-suspenders: if the persistent store was empty (first start of
    # the integration since this feature shipped, or store cleared), back-fill
    # from the device registry. Device `model` is set by camera.py:device_info
    # to the human-readable display name from models.py. Reverse-map it back
    # to the canonical hardwareVersion string so `_is_gen2()` works.
    # Wrapped in try/except: HA test fixtures sometimes hand back a partially-
    # initialised DeviceRegistry mock; rehydrate is best-effort.
    try:
        from homeassistant.helpers import device_registry as dr

        from .models import MODELS

        _dreg = dr.async_get(hass)
        _display_to_hw: dict[str, str] = {}
        for _hw_key, _cfg in MODELS.items():
            # First key wins per display name — keeps canonical Gen2 mapping
            # ("HOME_Eyes_Outdoor") instead of the "CAMERA_OUTDOOR_GEN2" alias.
            _display_to_hw.setdefault(_cfg.display_name, _hw_key)
        for _device in dr.async_entries_for_config_entry(_dreg, entry.entry_id):
            for _domain, _cid in _device.identifiers:
                if _domain != DOMAIN:
                    continue
                if _cid.upper() in coordinator.hw_version:
                    continue  # already populated
                _hw_from_model = _display_to_hw.get(_device.model or "")
                if _hw_from_model:
                    coordinator.hw_version[_cid.upper()] = _hw_from_model
                    _LOGGER.info(
                        "Recovered hardware version for %s from device registry: %s (%s)",
                        _cid[:8],
                        _hw_from_model,
                        _device.model,
                    )
    except Exception as exc:
        _LOGGER.debug("Device-registry hw_version rehydrate skipped: %s", exc)

    # First refresh — tolerate a cloud-side 5xx so the integration can still
    # set up entities for known cameras (loaded from the entity registry)
    # and the LAN-fallback paths can take over. Before v12.4.10 the bare
    # `async_config_entry_first_refresh()` raised `ConfigEntryNotReady` on
    # any cloud failure, which left the user with no usable entities for as
    # long as Bosch was down — even though privacy / light / LAN-ping all
    # work without the cloud. Now: try once, if it fails, fall back to
    # registry-derived cam_ids; the coordinator keeps retrying in the
    # background.
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as exc:
        _LOGGER.warning(
            "Bosch cloud unreachable on startup (%s) — bringing up integration "
            "with LAN-only entities; cloud-driven data will arrive on next refresh",
            exc,
        )
        cam_ids, cam_titles = _rehydrate_cams_from_registry(hass, entry.entry_id)
        if cam_ids:
            coordinator.data = {
                cid: {
                    "info": {"title": cam_titles.get(cid, cid)},
                    "status": "UNKNOWN",
                    "events": [],
                }
                for cid in cam_ids
            }
            coordinator.last_update_success = False
            _LOGGER.info(
                "Bosch cloud-degraded startup: rehydrated %d camera(s) from entity registry: %s",
                len(cam_ids),
                ", ".join(sorted(c[:8] for c in cam_ids)),
            )
            # Kick an immediate LAN ping so the LAN-reachable sensors and
            # switch fallbacks have a useful state right away.
            hass.async_create_task(coordinator.async_outage_ping_all())
        else:
            # Truly first-time install with no registry → preserve the original
            # behaviour and bail out so HA shows the standard setup-failed UI.
            raise

    # v12.3.0 migration — rename entity_ids carrying the v11.0.0 doubled-prefix
    # bug BEFORE forwarding platforms, so entities re-attach to the renamed
    # registry entries instead of re-creating with the buggy id. No-op on
    # clean / new installs and on installs that have already been migrated.
    await _migrate_doubled_prefix_entity_ids(hass, entry.entry_id)

    # v12.4.10 migration — the first BoschLanReachableBinarySensor build
    # overrode `name()` which doubled the device-name prefix into the
    # entity_id (`binary_sensor.bosch_<X>_bosch_<X>_lan_reachable`). Delete
    # any such stale entries so platform setup re-creates them with the
    # canonical `binary_sensor.bosch_<X>_lan_reachable` slug derived from
    # the translation key. No-op on clean installs.
    from homeassistant.helpers import entity_registry as er

    _ereg = er.async_get(hass)
    _stale_lan_ids = [
        e.entity_id
        for e in er.async_entries_for_config_entry(_ereg, entry.entry_id)
        if e.entity_id.endswith("_lan_reachable")
        and e.entity_id.count("_bosch_") >= 1
        and e.entity_id.startswith("binary_sensor.bosch_")
    ]
    for _stale_id in _stale_lan_ids:
        _LOGGER.info("v12.4.10 migration: removing stale entity_id %s", _stale_id)
        _ereg.async_remove(_stale_id)

    # v12.5.1 migration — Eyes Indoor II has no controllable light hardware
    # (only IR night-vision LEDs which the camera firmware manages itself).
    # v12.5.0 mistakenly created a `BoschFrontLight` entity for Indoor II
    # plus three stale `number.*_helligkeit_*` / `*_farbtemperatur_*`
    # entities had been left in the registry from an even older codepath.
    # All four were always `unavailable`. Remove them so the dashboard
    # doesn't show greyed-out entries that can never work. Per-cam scoped:
    # only entities whose unique_id contains an Indoor II cam_id are removed.
    _indoor_ii_cam_ids: set[str] = set()
    for _cam_id, _hw in (coordinator.hw_version or {}).items():
        if _hw in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
            _indoor_ii_cam_ids.add(_cam_id.lower())
    _orphan_uid_suffixes = (
        "_front_light_entity",  # BoschFrontLight (v12.5.0 mistake)
        "_top_led_brightness",  # BoschTopLedBrightnessNumber (Outdoor-only)
        "_bottom_led_brightness",  # BoschBottomLedBrightnessNumber (Outdoor-only)
        "_white_balance",  # BoschWhiteBalanceNumber (Outdoor-only)
    )
    _stale_indoor_ids: list[str] = []
    for _ent in er.async_entries_for_config_entry(_ereg, entry.entry_id):
        if not any(_ent.unique_id.lower().endswith(s) for s in _orphan_uid_suffixes):
            continue
        if not any(_cid in _ent.unique_id.lower() for _cid in _indoor_ii_cam_ids):
            continue
        _stale_indoor_ids.append(_ent.entity_id)
    for _stale_id in _stale_indoor_ids:
        _LOGGER.info(
            "v12.5.1 migration: removing Indoor II orphan entity %s (no light hardware)",
            _stale_id,
        )
        _ereg.async_remove(_stale_id)

    # Restore persisted daily AI budget so the cap survives restart/reload.
    await coordinator.async_load_ai_budget()

    # Quality-Scale Bronze (runtime-data): store on entry.runtime_data, not hass.data[DOMAIN].
    # HA clears runtime_data automatically on unload — no manual cleanup needed.
    entry.runtime_data = coordinator

    # Coord-independent options snapshot for _async_options_updated. Stored in
    # hass.data so the "did options change?" comparison survives the brief
    # runtime_data=None window during a reload — a data-only write (token / FCM)
    # landing in that window must not trigger a full reload. NOT cleared on
    # unload (would empty it inside the very window we protect); it is simply
    # overwritten by the next setup.
    hass.data.setdefault(OPTIONS_SNAPSHOT_KEY, {})[entry.entry_id] = get_options(entry)

    opts = get_options(entry)
    platforms = [p for p in ALL_PLATFORMS if p != "binary_sensor"]
    if opts.get("enable_binary_sensors", True):
        platforms = ["binary_sensor", *platforms]

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Start proactive background token refresh (5 min before JWT expiry).
    # Deliberately scheduled AFTER the awaits above succeed: arming this
    # timer earlier meant a failure in async_load_ai_budget() or
    # async_forward_entry_setups() aborted async_setup_entry with the timer
    # already live — HA never calls async_unload_entry (or fires
    # EVENT_HOMEASSISTANT_STOP, registered further below) for a setup that
    # never completed, so the handle had no cancellation path and fired
    # _proactive_refresh() later against an orphaned coordinator. Each failed
    # setup retry (HA retries on ConfigEntryNotReady) armed one more zombie
    # timer with no bound on how many could accumulate (bug-hunt 2026-07-03).
    coordinator.schedule_token_refresh()

    # Quench the camera-component log spam during stream pre-warm (idempotent).
    # See _StreamSupportNoiseFilter docstring for context.
    _install_stream_support_noise_filter()

    # Cloudflare-Tunnel HLS-buffering workaround (idempotent). Rewrites the
    # Content-Type on /api/hls/* responses so cloudflared switches to
    # streaming mode instead of buffering each segment at the edge — fixes
    # the iOS Companion App on cellular ("HLS wird geladen…" hang).
    # See cf_unbuffer.py docstring + knowledge-base/cloudflared-tunnel-hls-buffering.md
    from . import cf_unbuffer

    cf_unbuffer.register(hass)

    # Listen on HA's stream component logger for worker-error events. This
    # catches the auto-restart cycle from Stream._run_worker() — which our
    # own polling watchdog can miss when its tick lands during a brief
    # "available" window. See _StreamWorkerErrorListener for the full
    # reasoning. Only installs once per process regardless of reloads.
    stream_logger = logging.getLogger("homeassistant.components.stream")
    if not any(
        isinstance(h, _StreamWorkerErrorListener) for h in stream_logger.handlers
    ):
        listener = _StreamWorkerErrorListener(coordinator)
        stream_logger.addHandler(listener)
        coordinator.stream_log_listener = listener
    else:
        # Rebind the existing listener to the current coordinator so a
        # config reload doesn't leave it pointing at the old coordinator.
        existing = next(
            h
            for h in stream_logger.handlers
            if isinstance(h, _StreamWorkerErrorListener)
        )
        existing._coordinator = coordinator
        coordinator.stream_log_listener = existing

    # v8.0.2 migration: auto-enable front light / wallwasher / intensity entities
    # that were initially created with disabled_by=integration in earlier builds.
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)
    for uid_suffix in ("front_light_", "wallwasher_", "front_light_intensity_"):
        for cam_id in coordinator.data:
            uid = f"bosch_shc_{uid_suffix}{cam_id.lower()}"
            ent = ent_reg.async_get_entity_id(
                "switch" if "intensity" not in uid_suffix else "number", DOMAIN, uid
            )
            if ent:
                entry_obj = ent_reg.async_get(ent)
                if (
                    entry_obj
                    and entry_obj.disabled_by == er.RegistryEntryDisabler.INTEGRATION
                ):
                    ent_reg.async_update_entity(ent, disabled_by=None)
                    _LOGGER.info("v8.0.2 migration: enabled %s", ent)

    # Auto-setup go2rtc integration for WebRTC streaming (opt-out via options).
    # WHY the lock: if two config entries set up in parallel (e.g. after HA
    # restart with multiple accounts), both check "no go2rtc entry exists"
    # simultaneously and both fire async_init → duplicate go2rtc entries.
    # The domain-scoped asyncio.Lock serializes the check-and-create.
    # Stored on hass.data under a distinct key (not hass.data[DOMAIN]) so
    # it doesn't pollute the per-entry iteration in service handlers.
    if opts.get("enable_go2rtc", True):
        go2rtc_lock = hass.data.setdefault(f"{DOMAIN}_go2rtc_init_lock", asyncio.Lock())
        async with go2rtc_lock:
            go2rtc_entries = hass.config_entries.async_entries("go2rtc")
            if not go2rtc_entries:
                try:
                    result = await hass.config_entries.flow.async_init(
                        "go2rtc",
                        context={"source": "system"},
                        data={},
                    )
                    if result.get("type") == "create_entry":
                        _LOGGER.info(
                            "go2rtc integration auto-created for WebRTC streaming support"
                        )
                    else:
                        _LOGGER.debug(
                            "go2rtc setup result: %s", result.get("type", "unknown")
                        )
                except Exception as err:
                    _LOGGER.debug("go2rtc auto-setup skipped: %s", err)
            else:
                _LOGGER.debug(
                    "go2rtc integration already active (entry: %s)",
                    go2rtc_entries[0].entry_id,
                )

    # Reload integration when options change (e.g. scan_interval updated)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Cancel our long-running background tasks on HA shutdown. Without this
    # `async_unload_entry` does not run on HA stop (it only runs on config
    # entry unload/reload), so `_auto_renew_local_session` would still be
    # pending at HA's "final writes" shutdown stage and HA emits the
    # "was still running after final writes shutdown stage" warning plus a
    # 30 s close-event timeout. `async_listen_once` auto-unregisters after
    # firing, so there's no stale handler after a restart.
    async def _on_ha_stop(_event: Any) -> None:
        await _async_cancel_coordinator_tasks(coordinator)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_ha_stop)
    )

    # Start FCM supervisor (runs in background, non-blocking)
    if opts.get("enable_fcm_push", False):
        hass.async_create_task(coordinator.async_start_fcm_push())

    # Mini-NVR drain watcher — promotes finalized staging segments to the
    # configured storage target (local / smb / ftp). One watcher per
    # coordinator; serves all cameras. Cancelled in async_unload_entry.
    if opts.get("enable_nvr", False):
        coordinator.nvr_drain_task = hass.async_create_background_task(
            nvr_recorder.drain_staging_to_remote(coordinator),
            "bosch_nvr_drain_watcher",
        )

    # ── Webhook delivery ─────────────────────────────────────────────────────
    # Listen on all four HA event bus topics fired by the coordinator and
    # re-deliver them via HTTP POST to the user-configured URL.
    # Default OFF — both enable_webhook_delivery AND webhook_url must be set.
    _WEBHOOK_EVENT_TYPES = (
        "bosch_shc_camera_motion",
        "bosch_shc_camera_audio_alarm",
        "bosch_shc_camera_person",
        "bosch_shc_camera_intrusion",
    )

    async def _async_deliver_webhook(event: Any) -> None:
        """POST event payload to the configured webhook URL."""
        from .const import CONF_ENABLE_WEBHOOK_DELIVERY, CONF_WEBHOOK_URL

        cur_opts = get_options(entry)
        if not cur_opts.get(CONF_ENABLE_WEBHOOK_DELIVERY, False):
            return
        url = cur_opts.get(CONF_WEBHOOK_URL, "").strip()
        if not url:
            _LOGGER.warning(
                "Webhook delivery enabled but webhook_url is empty — skipping"
            )
            return
        # Only allow http(s) — refuse file://, gopher://, etc. that could be
        # smuggled in via the user option and abused through the shared session.
        if not url.lower().startswith(("http://", "https://")):
            _LOGGER.warning("Webhook URL rejected — only http(s) schemes are allowed")
            return
        payload: dict[str, Any] = {
            "event_type": event.event_type,
            "camera": event.data.get("camera_name", event.data.get("camera_id", "")),
            "camera_id": event.data.get("camera_id", ""),
            "timestamp": event.data.get("timestamp", ""),
            "extra": {
                k: v
                for k, v in event.data.items()
                if k not in ("camera_name", "camera_id", "timestamp")
            },
        }
        session = async_get_clientsession(hass)
        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status >= 400:
                    _LOGGER.warning(
                        "Webhook POST returned HTTP %d for event %s",
                        resp.status,
                        event.event_type,
                    )
                else:
                    _LOGGER.debug(
                        "Webhook POST %s → HTTP %d", event.event_type, resp.status
                    )
        except aiohttp.ClientError as err:
            _LOGGER.error("Webhook delivery failed for %s: %s", event.event_type, err)

    for _evt_type in _WEBHOOK_EVENT_TYPES:
        entry.async_on_unload(hass.bus.async_listen(_evt_type, _async_deliver_webhook))

    # describe_snapshot service — ask HA ai_task to describe a camera snapshot
    async def handle_describe_snapshot(call: ServiceCall) -> dict[str, Any]:
        """Ask HA's ai_task to describe the current camera snapshot."""
        import datetime as _dt_mod

        camera_id: str = call.data.get("camera_id", "").strip()
        entity_id_arg: str = call.data.get("entity_id", "").strip()
        instructions: str = call.data.get("instructions", "").strip()
        ai_task_entity_arg: str = call.data.get("ai_task_entity", "").strip()

        if not camera_id and not entity_id_arg:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id or entity_id"},
            )

        loaded = list(hass.config_entries.async_loaded_entries(DOMAIN))
        if not loaded:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_error",
                translation_placeholders={
                    "action": "describe_snapshot",
                    "error": "no loaded entries",
                },
            )
        resolved_entity_id: str = ""
        resolved_cam_id: str = ""
        coord: Any = None
        cur_opts: dict[str, Any] = {}
        for entry_inst in loaded:
            _coord = entry_inst.runtime_data
            if not _coord:
                continue
            if camera_id:
                cam_entity = getattr(_coord, "camera_entities", {}).get(camera_id)
                if cam_entity:
                    coord = _coord
                    cur_opts = get_options(entry_inst)
                    resolved_entity_id = cam_entity.entity_id
                    resolved_cam_id = camera_id
                    break
            elif entity_id_arg:
                for cid, cent in getattr(_coord, "camera_entities", {}).items():
                    if cent.entity_id == entity_id_arg:
                        coord = _coord
                        cur_opts = get_options(entry_inst)
                        resolved_entity_id = entity_id_arg
                        resolved_cam_id = cid
                        break
                if coord:
                    break
        if coord is None:
            # Fallback to first available coordinator for options
            for _fb_entry in loaded:
                if _fb_entry.runtime_data:
                    coord = _fb_entry.runtime_data
                    cur_opts = get_options(_fb_entry)
                    break
        if coord is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_error",
                translation_placeholders={
                    "action": "describe_snapshot",
                    "error": "no active coordinator",
                },
            )

        # Privacy guard: do not analyze a blank/privacy frame via the manual service
        if resolved_cam_id and coord.shc_state_cache.get(resolved_cam_id, {}).get(
            "privacy_mode"
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="privacy_active",
            )

        if not resolved_entity_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_found",
                translation_placeholders={
                    "kind": "camera entity",
                    "id": camera_id or entity_id_arg,
                },
            )

        prompt = instructions or cur_opts.get(
            "ai_describe_prompt",
            "Du bist eine Überwachungskamera-Assistenz. Melde NUR"
            " sicherheitsrelevante Beobachtungen: Personen (auch nur teilweise"
            " sichtbar: Beine, Arme, Silhouette, Schatten), Fahrzeuge, Tiere,"
            " Pakete oder ungewöhnliche Aktivität. Beschreibe NICHT die"
            " Umgebung, Räume, Möbel, Architektur oder Bildqualität und benenne"
            " KEINE Orte. Rate nicht: Fußmatten, Teppiche, Bodenfliesen und"
            " Schatten sind kein Paket. Wenn nichts Sicherheitsrelevantes"
            " erkennbar ist, sage das kurz, z. B.: Keine"
            " sicherheitsrelevanten Beobachtungen.",
        )
        # Language resolution: per-call override → option → fallback "Deutsch"
        language: str = (
            call.data.get("language", "").strip()
            or (cur_opts.get("ai_describe_language") or "").strip()
            or "Deutsch"
        )
        # Append bilingual language directive so the model replies in the chosen
        # language regardless of its training defaults.
        full_instructions: str = f"{prompt}\n\nRespond only in {language}. Antworte ausschließlich auf {language}."
        ai_task_entity_used: str = (
            ai_task_entity_arg or (cur_opts.get("ai_task_entity") or "").strip()
        )

        ai_call_data: dict[str, Any] = {
            "task_name": "Bosch camera snapshot",
            "instructions": full_instructions,
            "attachments": [
                {
                    "media_content_id": f"media-source://camera/{resolved_entity_id}",
                    "media_content_type": "image/jpeg",
                }
            ],
        }
        if ai_task_entity_used:
            ai_call_data["entity_id"] = ai_task_entity_used

        # Count this manual call as in-flight so a concurrent AUTO describe
        # (whose budget gate reads ``used + _ai_in_flight``) sees the work and
        # does not push the daily total over the cap. Service-path itself has no
        # budget gate (manual = always allowed), but it must stay visible.
        _track_in_flight = hasattr(coord, "ai_in_flight")
        if _track_in_flight:
            coord.ai_in_flight += 1
        try:
            async with asyncio.timeout(20):
                resp = await hass.services.async_call(
                    "ai_task",
                    "generate_data",
                    ai_call_data,
                    blocking=True,
                    return_response=True,
                )
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ai_task_unavailable",
                translation_placeholders={"error": "timed out (20s)"},
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ai_task_unavailable",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            if _track_in_flight:
                coord.ai_in_flight -= 1

        text: str = (
            str(resp.get("data", "")) if isinstance(resp, dict) else str(resp or "")
        ).strip()
        if not text:
            return {"description": ""}
        if resolved_cam_id:
            coord.ai_record_call(resolved_cam_id)
        generated_at = _dt_mod.datetime.now(_dt_mod.UTC).isoformat()
        if resolved_cam_id and resolved_cam_id in coord.data:
            coord.data[resolved_cam_id]["ai_description"] = {
                "text": text,
                "generated_at": generated_at,
                "ai_task_entity": ai_task_entity_used or "default",
            }
            coord.async_set_updated_data(coord.data)
        hass.bus.async_fire(
            "bosch_shc_camera_ai_description",
            {
                "camera_id": resolved_cam_id,
                "entity_id": resolved_entity_id,
                "description": text,
                "generated_at": generated_at,
            },
        )
        return {"description": text}

    # ── Auto-describe on motion (opt-in) ─────────────────────────────────────
    # _AI_MOTION_DEBOUNCE / _AI_MOTION_DEBOUNCE_SEC are module-level so the
    # debounce state survives integration reloads — see definition near the top.

    async def _async_auto_describe(event: Any) -> None:
        """Auto-call describe_snapshot on motion/person events (debounced)."""
        cam_id_evt: str = event.data.get("camera_id", "")
        now_ts = hass.loop.time()
        last = _AI_MOTION_DEBOUNCE.get(cam_id_evt, float("-inf"))
        if now_ts - last < _AI_MOTION_DEBOUNCE_SEC:
            return
        loaded_entries = list(hass.config_entries.async_loaded_entries(DOMAIN))
        if not loaded_entries:
            return
        # Resolve the correct coordinator for this camera before reading options.
        found_coord: Any = None
        for _entry in loaded_entries:
            coord_inst = _entry.runtime_data
            if coord_inst:
                cam_entity_obj = getattr(coord_inst, "camera_entities", {}).get(
                    cam_id_evt
                )
                if cam_entity_obj:
                    found_coord = coord_inst
                    break
        if found_coord is None:
            _LOGGER.debug("auto-describe: no entity found for cam_id %s", cam_id_evt)
            return
        ai_opts = get_options(found_coord.entry)
        if not ai_opts.get("ai_describe_on_motion", False):
            return
        # Update debounce timestamp only after confirming the option is enabled —
        # writing it before the check would suppress the first real describe call
        # if the user enables the option within the debounce window.
        _AI_MOTION_DEBOUNCE[cam_id_evt] = now_ts
        try:
            await found_coord.async_generate_ai_description(cam_id_evt, force=False)
        except Exception as err:
            _LOGGER.debug("auto-describe failed for %s: %s", cam_id_evt, err)

    for _motion_evt in ("bosch_shc_camera_motion", "bosch_shc_camera_person"):
        entry.async_on_unload(hass.bus.async_listen(_motion_evt, _async_auto_describe))

    if not hass.services.has_service(DOMAIN, "describe_snapshot"):
        hass.services.async_register(
            DOMAIN,
            "describe_snapshot",
            handle_describe_snapshot,
            supports_response=SupportsResponse.OPTIONAL,
        )

    # send_event_webhook service — test/manual trigger
    # Uses live-entry iteration so the handler always reads the current options
    # even after an integration reload — no stale closure over a setup-time entry.
    async def handle_send_event_webhook(call: ServiceCall) -> None:
        """Manually fire a webhook POST for testing."""
        import datetime as _dt

        from .const import CONF_ENABLE_WEBHOOK_DELIVERY, CONF_WEBHOOK_URL

        loaded = list(hass.config_entries.async_loaded_entries(DOMAIN))
        if not loaded:
            _LOGGER.warning(
                "send_event_webhook: no loaded entries for domain %s", DOMAIN
            )
            return
        cur_opts = get_options(loaded[0])
        if not cur_opts.get(CONF_ENABLE_WEBHOOK_DELIVERY, False):
            _LOGGER.warning(
                "send_event_webhook: webhook delivery is disabled in options"
            )
            return
        url = cur_opts.get(CONF_WEBHOOK_URL, "").strip()
        if not url:
            _LOGGER.warning("send_event_webhook: webhook_url is not configured")
            return
        if not url.lower().startswith(("http://", "https://")):
            _LOGGER.warning(
                "send_event_webhook: webhook_url %r has invalid scheme — only http/https allowed",
                url[:50],
            )
            return
        event_type_val: str = call.data.get("event_type", "MOVEMENT")
        entity_id_val: str = call.data.get("entity_id", "")
        # Resolve camera name from entity_id if given
        cam_name = entity_id_val
        if entity_id_val:
            state = hass.states.get(entity_id_val)
            if state:
                cam_name = state.attributes.get("friendly_name", entity_id_val)
        payload: dict[str, Any] = {
            "event_type": event_type_val,
            "camera": cam_name,
            "camera_id": "",
            "timestamp": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
            "extra": {"source": "manual"},
        }
        session = async_get_clientsession(hass)
        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                _LOGGER.info("send_event_webhook: POST %s → HTTP %d", url, resp.status)
        except aiohttp.ClientError as err:
            _LOGGER.error("send_event_webhook: POST failed: %s", err)

    if not hass.services.has_service(DOMAIN, "send_event_webhook"):
        hass.services.async_register(
            DOMAIN, "send_event_webhook", handle_send_event_webhook
        )

    return True


async def _async_cancel_coordinator_tasks(coord: BoschCameraCoordinator) -> None:
    """Shared teardown for both config-entry unload and HA stop.

    Called from `async_unload_entry` (integration reload / removal) and from
    the `EVENT_HOMEASSISTANT_STOP` listener registered in `async_setup_entry`.
    Without the stop listener, `_auto_renew_local_session` would still be
    running at HA's "final writes" shutdown stage and trigger the
    "was still running after final writes shutdown stage" warning — because
    `async_unload_entry` is not invoked on full HA shutdown, only on entry
    unload/reload.
    """
    # async_stop_fcm_push explicitly re-raises asyncio.CancelledError (it has
    # its own awaits on FCM client shutdown). If this whole teardown
    # coroutine is cancelled (e.g. HA's shutdown deadline cancelling a slow
    # unload) while sitting on THIS specific await — the only unguarded one
    # in this function, every step below already has its own try/except —
    # the CancelledError used to propagate immediately and skip every
    # remaining cleanup step: token-refresh handle, renewal/reaper tasks,
    # remaining _bg_tasks, the NVR drain watcher, NVR recorders, live-stream
    # teardown, Frigate endpoints, and stop_all_proxies. Catch it, finish the
    # rest of the cleanup, then re-raise at the end so the cancellation still
    # ultimately surfaces to the caller (bug-hunt 2026-07-03).
    # Set FIRST, before anything else (issue #47): once this is True,
    # start_recorder/_spawn_preroll_recorder_locked refuse to spawn a new
    # ffmpeg child (checked under the same per-cam _get_nvr_recorder_lock
    # that stop_all()/stop_all_preroll() below now also acquire), closing
    # the window where an in-flight recorder start could race a reload and
    # leave an untracked, never-killed process behind.
    coord.nvr_shutting_down = True
    _cancelled_during_cleanup: asyncio.CancelledError | None = None
    try:
        await coord.async_stop_fcm_push()
    except asyncio.CancelledError as err:
        _cancelled_during_cleanup = err
        _LOGGER.debug("FCM stop cancelled mid-teardown — continuing remaining cleanup")
    # Cancel scheduled proactive token refresh — otherwise a reload leaves
    # a stale TimerHandle that fires against the dead coordinator.
    handle = getattr(coord, "token_refresh_handle", None)
    if handle is not None:
        try:
            handle.cancel()
        except (AttributeError, RuntimeError) as err:
            _LOGGER.debug("Cancel of token-refresh handle raised: %s", err)
        coord.token_refresh_handle = None
    # Cancel all LOCAL session auto-renewal tasks. The task dicts also
    # register in _bg_tasks (via _replace_renewal_task), so the gather
    # below actually waits for cancellation to propagate.
    for task in coord.renewal_tasks.values():
        if not task.done():
            task.cancel()
    coord.renewal_tasks.clear()
    # Idle reaper tasks (same lifecycle as the renewal tasks above).
    for task in coord.reaper_tasks.values():
        if not task.done():
            task.cancel()
    coord.reaper_tasks.clear()
    # Cancel tracked fire-and-forget background tasks (snapshot refreshes
    # from FCM pushes, renewal tasks registered above, go2rtc registration,
    # etc.). Await them so cancellation actually propagates before HA
    # enters its own final-writes shutdown stage.
    bg = list(coord.bg_tasks)
    for t in bg:
        if not t.done():
            t.cancel()
    if bg:
        await asyncio.gather(*bg, return_exceptions=True)
    coord.bg_tasks.clear()
    # Stop the NVR drain watcher BEFORE the recorders. The watcher is a
    # long-running coroutine; cancelling it is the supported stop path.
    drain_task = getattr(coord, "nvr_drain_task", None)
    if drain_task is not None and not drain_task.done():
        drain_task.cancel()
        try:
            await drain_task
        except (
            asyncio.CancelledError,
            Exception,
        ):  # drain_task cancelled intentionally on shutdown; any residual error is non-actionable
            pass
        coord.nvr_drain_task = None
    # Stop all NVR recorders BEFORE the TLS proxies — once the proxies are
    # gone the ffmpeg children would die anyway, but we want a clean SIGTERM
    # so the trailing MP4 moov atom is flushed and the in-progress segment
    # stays playable.
    try:
        await nvr_recorder.stop_all(coord)
    except Exception as err:
        _LOGGER.debug("NVR stop_all on unload raised: %s", err)
    # Tear down every active LOCAL/REMOTE live stream cleanly BEFORE
    # stop_all_proxies. Without this, integration reload leaves stale state
    # behind: go2rtc keeps the producer URL with the now-dead proxy port,
    # and HA's Stream object on the camera entity keeps the dead URL —
    # the browser then polls a 404 m3u8 until the user hard-refreshes the
    # card. _tear_down_live_stream handles per-cam: unregister go2rtc,
    # stop_tls_proxy, stream.stop() + cam_entity.stream = None.
    # Symptom hit 2026-05-26 after two mjpeg-test reloads back-to-back left
    # a stale `cbs-76512325@127.0.0.1:32987` Terrasse entry in go2rtc that
    # had to be cleaned manually.
    # `getattr(..., {})` keeps minimal SimpleNamespace test fixtures working —
    # they often don't populate every coordinator attribute.
    for cam_id in list(getattr(coord, "live_connections", {}).keys()):
        teardown = getattr(coord, "tear_down_live_stream", None)
        if teardown is None:
            break
        try:
            await teardown(cam_id)
        except Exception as err:
            _LOGGER.debug(
                "teardown live stream for %s on unload raised: %s",
                cam_id[:8],
                err,
            )
    # Stop all Frigate front-doors (closes listeners + the shared bg loop).
    stop_frigate = getattr(coord, "async_stop_frigate_endpoints", None)
    if stop_frigate is not None:
        stop_frigate()  # self-guarded — never raises
    # Stop all main-viewing-path front-doors (viewing_front_door.py) —
    # same rationale as the Frigate front-doors above, separate runner.
    viewing_runner = getattr(coord, "viewing_front_door_runner", None)
    if viewing_runner is not None:
        try:
            viewing_runner.stop_all()
        except Exception as err:
            _LOGGER.debug("viewing front-door stop_all on unload raised: %s", err)
        coord.viewing_front_door_runner = None
    # Same for the REMOTE viewing-path front-door (remote_viewing_front_door.py)
    # — separate runner, same unload rationale.
    remote_viewing_runner = getattr(coord, "remote_viewing_front_door_runner", None)
    if remote_viewing_runner is not None:
        try:
            remote_viewing_runner.stop_all()
        except Exception as err:
            _LOGGER.debug(
                "REMOTE viewing front-door stop_all on unload raised: %s", err
            )
        coord.remote_viewing_front_door_runner = None
    # Close the shared go2rtc-API session (Work Package 1,
    # stream-perf-stability-refactor) — opened lazily on first
    # register/unregister/consumer-count call. Distinct from the
    # Bosch-cloud session in cloud_ssl.py, which closes itself on
    # EVENT_HOMEASSISTANT_STOP; this one is coordinator-scoped so it is
    # closed here on both unload and HA stop. The live-stream teardown loop
    # above already ran every per-cam go2rtc unregister, so it's safe to
    # close now. `getattr` keeps minimal SimpleNamespace test fixtures
    # (predating this attribute) working unchanged.
    go2rtc_session = getattr(coord, "go2rtc_session", None)
    if go2rtc_session is not None and not go2rtc_session.closed:
        try:
            await go2rtc_session.close()
        except Exception as err:
            _LOGGER.debug("go2rtc session close on unload raised: %s", err)
    if hasattr(coord, "go2rtc_session"):
        coord.go2rtc_session = None
    # Mark teardown done BEFORE returning so any straggler call to
    # _get_go2rtc_session that races this function (e.g. a live frontend
    # stream_source() request landing in the gap between this call and
    # async_unload_entry's later async_unload_platforms) raises instead of
    # lazily minting a session nothing will ever close again.
    coord.go2rtc_teardown_done = True
    # Mark BEFORE the sweep below for the same reason as
    # _go2rtc_teardown_done just above: a straggler start_tls_proxy_wiring
    # call racing this point (e.g. a queued task) must refuse to start a
    # fresh proxy that stop_all_proxies's already-taken snapshot can never
    # see, rather than silently surviving past config-entry unload.
    coord.tls_proxy_teardown_done = True
    # Stop all TLS proxies (closes asyncio.Server objects).
    # Idempotent — _tear_down_live_stream already stopped per-cam proxies,
    # this catches anything left in the server_cache (defensive).
    # `getattr(..., {})` keeps minimal SimpleNamespace test fixtures
    # (predating this attribute) working unchanged, matching the pattern
    # used throughout this function.
    await stop_all_proxies(
        coord.tls_proxy_ports, getattr(coord, "tls_proxy_servers", {})
    )
    # Remove the stream-worker log listener so the handler doesn't outlive
    # the coordinator and keep a reference to a dead object.
    listener = getattr(coord, "stream_log_listener", None)
    if listener is not None:
        logging.getLogger("homeassistant.components.stream").removeHandler(listener)
        # Nullify the coordinator reference so any in-flight emit() calls
        # during the reload gap bail out early instead of accessing a dead object.
        listener._coordinator = None
        coord.stream_log_listener = None

    if _cancelled_during_cleanup is not None:
        # Cleanup finished despite the cancellation — now let it surface to
        # the caller, matching standard asyncio cancellation etiquette.
        raise _cancelled_during_cleanup


async def async_unload_entry(
    hass: HomeAssistant, entry: BoschCameraConfigEntry
) -> bool:
    """Unload a Bosch Smart Home Camera config entry."""
    coord = getattr(entry, "runtime_data", None)
    if coord:
        await _async_cancel_coordinator_tasks(coord)

    return bool(await hass.config_entries.async_unload_platforms(entry, ALL_PLATFORMS))


async def _async_options_updated(
    hass: HomeAssistant, entry: BoschCameraConfigEntry
) -> None:
    """Reload the config entry only when the *options* actually change.

    This listener fires on ANY config-entry update — including the frequent
    data-only writes (token refresh at L1560, plus five FCM `data=` writes in
    fcm.py). A data-only write must NEVER reload: a reload tears down every
    camera's live stream (go2rtc unregister + TLS-proxy stop). Incident
    2026-05-29: toggling privacy on one camera persisted a refreshed token, this
    listener fired while `entry.runtime_data` was briefly None, the old
    `if coord:` guard fell through straight to async_reload, and an unrelated
    camera's WebRTC source vanished from go2rtc (DESCRIBE 404 → 30 s-delayed HLS).

    The reload decision must depend ONLY on whether options changed — never on
    whether the coordinator happens to be present. The previous-options snapshot
    therefore lives in hass.data (keyed by entry_id) so it survives the
    `runtime_data is None` reload/startup window; the coordinator snapshot is a
    fallback for the first push before hass.data is populated. See
    OPTIONS_SNAPSHOT_KEY + the snapshot write in async_setup_entry.
    """
    new_opts = get_options(entry)
    prev_opts: dict[str, Any] | None = None
    snapshots = hass.data.get(OPTIONS_SNAPSHOT_KEY)
    if isinstance(snapshots, dict):
        stored = snapshots.get(entry.entry_id)
        if isinstance(stored, dict):
            prev_opts = stored
    if prev_opts is None:
        # Fallback for the first update before async_setup_entry stored the
        # hass.data snapshot (and for tests that only populate runtime_data).
        coord = getattr(entry, "runtime_data", None)
        coord_snap = (
            getattr(coord, "_options_snapshot", None) if coord is not None else None
        )
        if isinstance(coord_snap, dict):
            prev_opts = coord_snap
    if prev_opts is not None and prev_opts == new_opts:
        _LOGGER.debug(
            "Config entry updated (options unchanged — data-only write) — skipping reload"
        )
        return
    # Real options change (or previous options unknown → safest to reload).
    # Record the new options before reloading so the fresh setup compares
    # against them rather than re-reloading in a loop.
    if isinstance(snapshots, dict):
        snapshots[entry.entry_id] = new_opts
    await hass.config_entries.async_reload(entry.entry_id)
