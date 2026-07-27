"""Bosch Smart Home Camera — Home Assistant Integration.

TRUE MINIMAL v1: camera platform only. Provides a snapshot-only camera
entity per Bosch Smart Home camera via the Bosch Cloud API
(residential.cbs.boschsecurity.com) — latest motion-triggered JPEG plus
on-demand snapshot fetch. No live streaming, no FCM push, no additional
platforms.

Setup: Settings → Integrations → Add → "Bosch Smart Home Camera", then log
in via Bosch SingleKey ID (OAuth2 / application_credentials).

No user data is hardcoded. All configuration via the HA UI.
"""

import asyncio
import logging
import re as _re_mod
import time
from typing import Any

from bosch_shc_camera_client.auth_utils import (
    async_digest_request as async_digest_request,  # re-export: mypy --no-implicit-reexport (coordinator.py imports it via `from . import`)
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession as async_get_clientsession,  # re-export: mypy --no-implicit-reexport (coordinator.py imports it via `from . import`)
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .cloud_ssl import (
    async_get_bosch_cloud_session as async_get_bosch_cloud_session,  # re-export: mypy --no-implicit-reexport (token_auth.py imports it via `from . import`)
)
from .const import (
    CLOUD_API as CLOUD_API,  # re-export: mypy --no-implicit-reexport (coordinator.py imports it via `from . import`)
    DEFAULT_OPTIONS as DEFAULT_OPTIONS,  # re-export: mypy --no-implicit-reexport (config_flow.py imports it via `from . import`)
    DOMAIN,
)
from .coordinator import (
    BoschCameraCoordinator as BoschCameraCoordinator,  # re-export: mypy --no-implicit-reexport (platform modules import it via `from . import`)
    _is_safe_bosch_url as _is_safe_bosch_url,  # re-export: mypy --no-implicit-reexport (camera.py imports it via `from . import`)
    get_options as get_options,  # re-export: mypy --no-implicit-reexport (camera.py imports it via `from . import`)
)
from .models import MODELS
from .snapshot_store import async_remove_all_snapshots

_LOGGER = logging.getLogger(__name__)

# FCM_DELIVERY_DEAD_AFTER_SEC moved to const.py — shared with event_dispatch.py.

# SLOW_TIER_MAX_DEFER_SEC moved to const.py — shared with slow_tier.py.

# _FRESH_SNAP_TTL / FCM_DOWN_EVENT_POLL_SEC / CAMERA_OFFLINE_ANNOUNCE_GRACE_SEC
# moved to coordinator.py — only used by BoschCameraCoordinator.


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


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Minimal v1: camera platform only (snapshot-fetch). Only camera.py remains.
PLATFORMS = ["camera"]

# hass.data key holding the per-entry options snapshot used by
# _async_options_updated to tell a real options edit apart from the frequent
# data-only writes (token refresh, FCM token/credential persistence). Kept in
# hass.data (not only on the coordinator) so the comparison survives the brief
# `entry.runtime_data is None` window during a reload — see _async_options_updated.
OPTIONS_SNAPSHOT_KEY = f"{DOMAIN}_options_snapshot"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration (import the default OAuth2 client credential)."""
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
    from .config_flow import CLIENT_ID, CLIENT_SECRET  # noqa: PLC0415

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Bosch SingleKey ID"),
    )

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to the current schema version.

    v1 → v2 (2026-05-17, v12.4.3): DEFAULT_OPTIONS['stream_connection_type']
    flipped from 'auto' to 'local'. Entries that never explicitly set the
    option silently relied on the auto default; without this migration they
    would switch to local-only on first start after upgrade and lose their
    REMOTE-fallback safety net. Persist 'auto' explicitly so existing
    installs keep their current behaviour. New installs (created after the
    bump) get 'local' via DEFAULT_OPTIONS.

    v2 → v3 (2026-05-18, v12.4.5): version bump only. The original step here
    migrated a now-removed `fcm_push_mode` option (FCM push isn't part of
    this snapshot-only build) — kept as a no-op version bump so existing
    entries created under v1/v2 still reach `config_flow.VERSION = 3`
    without HA re-running the v1→v2 step a second time.

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
        final_version = 3

    if final_version != starting_version:
        hass.config_entries.async_update_entry(
            entry, options=new_options, data=new_data, version=final_version
        )
    return True


async def _async_load_persisted_caches(
    hass: HomeAssistant, coordinator: BoschCameraCoordinator
) -> None:
    """Load every persisted cross-restart cache onto ``coordinator``.

    Covers the cloud-outage-notified flag, LAN-IP map, hardware-version map,
    and LOCAL Digest creds — all written back on every successful refresh,
    read here so LAN-fallback paths have something to work with on a
    cloud-degraded cold start.
    """
    cloud_alert_store: Store = Store(hass, version=1, key=f"{DOMAIN}_cloud_alert_state")
    coordinator.cloud_alert_store = cloud_alert_store
    _persisted_cloud_alert = await cloud_alert_store.async_load() or {}
    if (
        isinstance(_persisted_cloud_alert, dict)
        and _persisted_cloud_alert.get("outage_notified") is True
    ):
        coordinator.cloud_outage_notified = True
        _LOGGER.info(
            "Loaded persisted cloud-outage-notified flag (was True at last save)",
        )

    lan_ips_store: Store = Store(hass, version=1, key=f"{DOMAIN}_lan_ips")
    coordinator.lan_ips_store = lan_ips_store
    _persisted_ips = await lan_ips_store.async_load() or {}
    if isinstance(_persisted_ips, dict):
        for _cid, _ip in _persisted_ips.items():
            if isinstance(_cid, str) and isinstance(_ip, str):
                coordinator.rcp_lan_ip_cache[_cid.upper()] = _ip
        if _persisted_ips:
            _LOGGER.info(
                "Loaded %d persisted LAN IP(s) for cloud-degraded LAN ping",
                len(_persisted_ips),
            )

    # v12.4.10 added the LAN-fallback availability gate but missed hw_version
    # persistence; without it a cold start during a Bosch cloud 5xx leaves
    # `_is_gen2()` returning False for every camera, breaking privacy /
    # front-light switch availability even though the LAN RCP path works.
    hw_version_store: Store = Store(hass, version=1, key=f"{DOMAIN}_hw_versions")
    coordinator.hw_version_store = hw_version_store
    _persisted_hw = await hw_version_store.async_load() or {}
    if isinstance(_persisted_hw, dict):
        for _cid, _hw in _persisted_hw.items():
            if isinstance(_cid, str) and isinstance(_hw, str):
                coordinator.hw_version[_cid.upper()] = _hw
        if _persisted_hw:
            _LOGGER.info(
                "Loaded %d persisted hardware version(s) for cloud-degraded LAN fallback",
                len(_persisted_hw),
            )

    # Bosch cycles LOCAL Digest creds on every PUT /connection LOCAL.
    # Security note: stored in HA's .storage (same protection level as the
    # cloud bearer token). LAN-only effective scope (camera not internet-exposed).
    # private=True: Store defaults to mode 0644 (world-readable) — this file
    # holds each camera's plaintext Digest username/password, so it must be
    # written with the same restrictive mode HA's other credential stores use
    # (bug-hunt 2026-07-27, Copilot review round 5).
    _creds_store: Store = Store(
        hass, version=1, key=f"{DOMAIN}_local_creds", private=True
    )
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


async def _async_rehydrate_hw_from_registry(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BoschCameraCoordinator
) -> None:
    """Back-fill hw_version from the device registry if the store was empty.

    Belt-and-suspenders for the first start of the integration since
    hw_version persistence shipped, or a cleared store. Device `model` is set
    by camera.py:device_info to the human-readable display name from
    models.py; reverse-mapped here to the canonical hardwareVersion string so
    `_is_gen2()` works. Best-effort: HA test fixtures sometimes hand back a
    partially-initialised DeviceRegistry mock.
    """
    try:
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
    except Exception as exc:  # noqa: BLE001 — best-effort registry rehydrate; a malformed/unexpected registry entry must not block startup
        _LOGGER.debug("Device-registry hw_version rehydrate skipped: %s", exc)


async def _async_first_refresh_with_fallback(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BoschCameraCoordinator
) -> None:
    """Do the first coordinator refresh, tolerating a cloud-side 5xx.

    Before v12.4.10 the bare `async_config_entry_first_refresh()` raised
    `ConfigEntryNotReady` on any cloud failure, leaving the user with no
    usable entities for as long as Bosch was down — even though privacy /
    light / LAN-ping all work without the cloud. Try once; on failure, fall
    back to registry-derived cam_ids so LAN-fallback paths can take over
    while the coordinator keeps retrying in the background. Re-raises when
    there's no registry to fall back to (truly first-time install), so HA
    shows the standard setup-failed UI.
    """
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as exc:
        _LOGGER.warning(
            "Bosch cloud unreachable on startup (%s) — bringing up integration "
            "with LAN-only entities; cloud-driven data will arrive on next refresh",
            exc,
        )
        cam_ids, cam_titles = _rehydrate_cams_from_registry(hass, entry.entry_id)
        if not cam_ids:
            raise
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
        # Tracked (not a bare hass.async_create_task) so a removal/reload
        # immediately after this degraded setup cancels and awaits it
        # instead of leaving it running against an already-torn-down
        # coordinator (Copilot review round 10).
        coordinator.spawn_tracked(
            coordinator.async_outage_ping_all(), name="bosch_shc_camera_startup_ping"
        )


async def _async_run_post_refresh_migrations(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BoschCameraCoordinator
) -> None:
    """Run the entity-registry migrations that must land before platform setup."""
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
    _ereg = er.async_get(hass)
    _stale_lan_ids = [
        e.entity_id
        for e in er.async_entries_for_config_entry(_ereg, entry.entry_id)
        if e.entity_id.endswith("_lan_reachable")
        and e.entity_id.count("_bosch_") >= 1
        and e.entity_id.startswith("binary_sensor.bosch_")
    ]
    for _stale_id in _stale_lan_ids:
        _LOGGER.info("Migration v12.4.10: removing stale entity_id %s", _stale_id)
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
            "Migration v12.5.1: removing Indoor II orphan entity %s (no light hardware)",
            _stale_id,
        )
        _ereg.async_remove(_stale_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch Smart Home Camera from a config entry."""
    coordinator = BoschCameraCoordinator(hass, entry)

    await _async_load_persisted_caches(hass, coordinator)
    await _async_rehydrate_hw_from_registry(hass, entry, coordinator)
    await _async_first_refresh_with_fallback(hass, entry, coordinator)
    await _async_run_post_refresh_migrations(hass, entry, coordinator)

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start proactive background token refresh (5 min before JWT expiry).
    # Deliberately scheduled AFTER the awaits above succeed: arming this
    # timer earlier meant a failure in
    # async_forward_entry_setups() aborted async_setup_entry with the timer
    # already live — HA never calls async_unload_entry (or fires
    # EVENT_HOMEASSISTANT_STOP, registered further below) for a setup that
    # never completed, so the handle had no cancellation path and fired
    # _proactive_refresh() later against an orphaned coordinator. Each failed
    # setup retry (HA retries on ConfigEntryNotReady) armed one more zombie
    # timer with no bound on how many could accumulate (bug-hunt 2026-07-03).
    coordinator.schedule_token_refresh()

    # Reload integration when options change (e.g. scan_interval updated)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Cancel our long-running background tasks on HA shutdown. Without this
    # `async_unload_entry` does not run on HA stop (it only runs on config
    # entry unload/reload), so `auto_renew_local_session` would still be
    # pending at HA's "final writes" shutdown stage and HA emits the
    # "was still running after final writes shutdown stage" warning plus a
    # 30 s close-event timeout. `async_listen_once` auto-unregisters after
    # firing, so there's no stale handler after a restart.
    async def _on_ha_stop(_event: Any) -> None:
        await _async_cancel_coordinator_tasks(coordinator)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_ha_stop)
    )

    return True


async def _async_cancel_coordinator_tasks(coord: BoschCameraCoordinator) -> None:
    """Shared teardown for both config-entry unload and HA stop.

    Called from `async_unload_entry` (integration reload / removal) and from
    the `EVENT_HOMEASSISTANT_STOP` listener registered in `async_setup_entry`.
    Without the stop listener, the proactive token-refresh timer would still
    be pending at HA's "final writes" shutdown stage and trigger the
    "was still running after final writes shutdown stage" warning — because
    `async_unload_entry` is not invoked on full HA shutdown, only on entry
    unload/reload.

    Snapshot-only build: only the proactive token-refresh timer needs
    cancelling here. The old live-streaming feature set's background-task
    teardown (LOCAL session auto-renewal, idle reapers, the streaming-proxy
    API session, the stream-worker log listener) no longer applies.
    """
    # Cancel scheduled proactive token refresh — otherwise a reload leaves
    # a stale TimerHandle that fires against the dead coordinator.
    handle = getattr(coord, "token_refresh_handle", None)
    if handle is not None:
        try:
            handle.cancel()
        except (AttributeError, RuntimeError) as err:
            _LOGGER.debug("Cancel of token-refresh handle raised: %s", err)
        coord.token_refresh_handle = None
    # Cancel any tracked fire-and-forget background tasks (e.g. snapshot
    # refreshes). Await them so cancellation actually propagates before HA
    # enters its own final-writes shutdown stage.
    bg_tasks = getattr(coord, "bg_tasks", None)
    if bg_tasks:
        bg = list(bg_tasks)
        for t in bg:
            if not t.done():
                t.cancel()
        await asyncio.gather(*bg, return_exceptions=True)
        bg_tasks.clear()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and cancel any background coordinator tasks."""
    coord = getattr(entry, "runtime_data", None)
    if coord:
        await _async_cancel_coordinator_tasks(coord)

    return bool(await hass.config_entries.async_unload_platforms(entry, PLATFORMS))


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete every integration-owned on-disk file when the entry is removed.

    Called only on full config-entry removal — never on a reload/unload,
    which must leave this state intact. Without this, the four Store files
    (cloud-outage-notified flag, LAN IPs, hardware versions, LOCAL Digest
    credentials) and the persisted-snapshot JPEG directory all retained LAN
    credentials and camera images indefinitely after removal (bug-hunt
    2026-07-27, Copilot review round 5).
    """
    for key in (
        f"{DOMAIN}_cloud_alert_state",
        f"{DOMAIN}_lan_ips",
        f"{DOMAIN}_hw_versions",
        f"{DOMAIN}_local_creds",
    ):
        await Store(hass, version=1, key=key).async_remove()
    await async_remove_all_snapshots(hass)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry only when the *options* actually change.

    This listener fires on ANY config-entry update — including the frequent
    data-only writes (token refresh). A data-only write must NEVER reload:
    reloading tears down and re-creates every camera entity. Incident
    2026-05-29 (pre-dating this snapshot-only rebuild, when the integration
    still owned live streaming): toggling privacy on one camera persisted a
    refreshed token, this listener fired while `entry.runtime_data` was
    briefly None, the old `if coord:` guard fell through straight to
    async_reload, and an unrelated camera's live stream dropped for ~30s.

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
