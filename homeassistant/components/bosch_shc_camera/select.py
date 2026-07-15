"""Select entities for Bosch Smart Home Camera integration.

Provides:
  - BoschVideoQualitySelect: dropdown to choose streaming quality
  - BoschMotionSensitivitySelect: dropdown to set motion detection sensitivity
    (SUPER_HIGH / HIGH / MEDIUM / MEDIUM_LOW / LOW)
    Reads from coordinator.motion_settings(cam_id)["motionAlarmConfiguration"].
    Writes via PUT /v11/video_inputs/{id}/motion.
    Disabled by default.
"""

import logging
import time
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschCameraConfigEntry, BoschCameraCoordinator
from .const import CONF_ENABLE_PTZ_CONTROLS, DOMAIN
from .guards import _is_gen2_indoor, _warn_if_privacy_on
from .models import get_model_config

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

STREAM_MODE_OPTIONS = ["auto", "local", "remote"]

QUALITY_OPTIONS = ["auto", "high", "low"]

NVR_MODE_OPTIONS = ["continuous", "event_buffered"]

MOTION_SENSITIVITY_OPTIONS = [
    "super_high",
    "high",
    "medium_high",
    "medium_low",
    "low",
    "off",
]
SENSITIVITY_TO_API = {k: k.upper() for k in MOTION_SENSITIVITY_OPTIONS}

DETECTION_MODE_OPTIONS = ["all_motions", "only_humans", "zones"]
DETECTION_TO_API = {k: k.upper() for k in DETECTION_MODE_OPTIONS}

FCM_PUSH_MODE_OPTIONS = ["auto", "polling"]

# Pan preset options and their mapped angles (degrees from centre).
# Available only for cameras with panLimit > 0 (CAMERA_360 indoor).
PAN_PRESET_OPTIONS = ["home", "left", "right", "back_left", "back_right"]
PAN_PRESET_ANGLES: dict[str, int] = {
    "home": 0,
    "left": -60,
    "right": 60,
    "back_left": -120,
    "back_right": 120,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for each camera and the integration."""
    coordinator: BoschCameraCoordinator = config_entry.runtime_data
    entities: list[SelectEntity] = []
    for cam_id in coordinator.data:
        entities.append(BoschVideoQualitySelect(coordinator, cam_id, config_entry))
        entities.append(BoschMotionSensitivitySelect(coordinator, cam_id, config_entry))
        # Gen2-only: detection mode select
        cam_info = coordinator.data[cam_id].get("info", {})
        hw = cam_info.get("hardwareVersion", "CAMERA")
        if get_model_config(hw).generation >= 2:
            entities.append(BoschDetectionModeSelect(coordinator, cam_id, config_entry))
        # PTZ preset select — only for cameras with panLimit > 0 (CAMERA_360 indoor)
        # AND opt-in via options. Default off so non-PTZ users see no extra entity.
        pan_limit = cam_info.get("featureSupport", {}).get("panLimit", 0)
        ptz_enabled = config_entry.options.get(CONF_ENABLE_PTZ_CONTROLS, False)
        if pan_limit and ptz_enabled:
            entities.append(
                BoschPanPresetSelect(coordinator, cam_id, config_entry, pan_limit)
            )
        # Per-camera Mini-NVR mode override (GitHub #43) — only relevant once
        # Mini-NVR itself is enabled (same gate as BoschNvrRecordingSwitch).
        if config_entry.options.get("enable_nvr", False):
            entities.append(BoschNvrModeSelect(coordinator, cam_id, config_entry))
    # Integration-level selects (one per integration, not per camera)
    first_cam_id = next(iter(coordinator.data), None)
    if first_cam_id:
        entities.append(BoschFcmPushModeSelect(coordinator, first_cam_id, config_entry))
        entities.append(BoschStreamModeSelect(coordinator, first_cam_id, config_entry))
    async_add_entities(entities)


class BoschVideoQualitySelect(
    CoordinatorEntity[BoschCameraCoordinator], SelectEntity, RestoreEntity
):
    """Select entity to choose the RTSPS stream quality (inst + highQualityVideo)."""

    _attr_has_entity_name = True
    _attr_options = QUALITY_OPTIONS

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the video quality select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        cam_data = coordinator.data.get(cam_id, {})
        cam_info = cam_data.get("info", {})
        self._cam_title = cam_info.get("title", cam_id)
        self._entry = entry
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_video_quality"
        self._attr_translation_key = "video_quality"
        self._attr_entity_category = EntityCategory.CONFIG

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last quality selection after HA restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            saved = last_state.state
            # Backward compat: old states were display text like "Auto"
            _legacy_map = {
                "Auto": "auto",
                "Hoch (30 Mbps)": "high",
                "Niedrig (1.9 Mbps)": "low",
            }
            quality_key = _legacy_map.get(
                saved, saved if saved in QUALITY_OPTIONS else None
            )
            if quality_key:
                self.coordinator.set_quality(self._cam_id, quality_key)
                _LOGGER.debug("Restored quality %s for %s", quality_key, self._cam_id)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str:
        """Return the current quality key."""
        quality_key = self.coordinator.get_quality(self._cam_id)
        return quality_key if quality_key in QUALITY_OPTIONS else "auto"

    @override
    async def async_select_option(self, option: str) -> None:
        """Handle quality selection — update coordinator preference and reconnect stream."""
        self.coordinator.set_quality(self._cam_id, option)
        # If stream is currently active, reconnect with new quality.
        # go2rtc re-registration is no longer done explicitly here —
        # try_live_connection's own try_live_connection_inner already pushes
        # WebRTC provider discovery after a successful (re)connect, and
        # HA-core's bundled go2rtc provider auto-registers whatever
        # stream_source() returns on the next WebRTC offer (both LOCAL and
        # REMOTE front-doors publish a stable URL, so this stays a cheap,
        # dedup-friendly no-op re-add rather than a fresh leaked entry).
        live = self.coordinator.data.get(self._cam_id, {}).get("live", {})
        if live.get("rtspsUrl") or live.get("proxyUrl"):
            try:
                new_live = await self.coordinator.try_live_connection(self._cam_id)
                if new_live:
                    self.coordinator.data[self._cam_id]["live"] = new_live
            except Exception:  # noqa: BLE001 — best-effort live-URL reconnect on quality change, failure non-actionable
                pass
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschNvrModeSelect(
    CoordinatorEntity[BoschCameraCoordinator], SelectEntity, RestoreEntity
):
    """Select entity to override the Mini-NVR recording mode for one camera.

    GitHub #43 (realKim-dotcom): lets a mixed fleet run different NVR
    strategies per camera instead of one global `nvr_event_only` flag —
    e.g. a glass-facing camera (PIR never fires through glass) wants
    always-on recording instead of motion-gated, while a premises camera
    wants a lightweight event-buffered pre-roll ring instead of 24/7 capture.

    SCOPE (bug-hunt finding, 2026-07-11 — documented honestly rather than
    silently narrowed): "Continuous" here means the existing always-on
    behavior, NOT the alarm-armed-gated recording the original issue
    describes ("continuous while armed") — this integration has no
    alarm-state-aware recording gate today. A per-camera `nvr_preroll_seconds`
    override (the issue's second ask, so different event-buffered cameras
    could each pick their own buffer size) is also not implemented; all
    event-buffered cameras still share the one global preroll-seconds value.
    Both are reasonable v1 follow-ups, not silently dropped.

    No "off" option: the existing BoschNvrRecordingSwitch already turns
    Mini-NVR on/off per camera — a third redundant "off" mode here would
    just duplicate that switch and confuse which one is authoritative.
    """

    _attr_has_entity_name = True
    _attr_options = NVR_MODE_OPTIONS
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the NVR mode select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        cam_data = coordinator.data.get(cam_id, {})
        cam_info = cam_data.get("info", {})
        self._cam_title = cam_info.get("title", cam_id)
        self._entry = entry
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_nvr_mode"
        self._attr_translation_key = "nvr_mode"
        self._attr_entity_category = EntityCategory.CONFIG

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last NVR mode override after HA restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in NVR_MODE_OPTIONS:
            self.coordinator.set_nvr_mode(self._cam_id, last_state.state)
            _LOGGER.debug("Restored NVR mode %s for %s", last_state.state, self._cam_id)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str:
        """Return the effective mode (per-cam override, or the global fallback)."""
        mode = self.coordinator.get_nvr_mode(self._cam_id)
        return mode if mode in NVR_MODE_OPTIONS else "continuous"

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the per-camera NVR mode override, applying it immediately if running.

        Bug-hunt finding (2026-07-11): an earlier version of this docstring
        claimed the change would "take effect on the next credential
        rotation" — but v14.5.4 removed the proactive cred-rotation restart
        entirely (LOCAL sessions now survive indefinitely without it), so a
        camera with a long-running healthy recorder could get stuck on the
        old mode with no natural trigger ever picking up the new one. Restart
        explicitly instead, reusing the same idempotent respawn path
        `BoschNvrRecordingSwitch.async_turn_on` uses — safe to call even
        though it also (redundantly, since it's already true) sets
        `_nvr_user_intent`, because it's gated on "recorder already active"
        so it can never turn NVR ON for a camera whose switch is off.
        """
        self.coordinator.set_nvr_mode(self._cam_id, option)
        recorder_active = (
            self._cam_id in self.coordinator.nvr_processes
            or self._cam_id in self.coordinator.nvr_preroll_processes
        )
        if recorder_active:
            await self.coordinator.start_recorder(self._cam_id)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschMotionSensitivitySelect(
    CoordinatorEntity[BoschCameraCoordinator], SelectEntity
):
    """Select entity to set motion detection sensitivity for a camera.

    Options: SUPER_HIGH / HIGH / MEDIUM / MEDIUM_LOW / LOW
    Reads from coordinator.motion_settings(cam_id)["motionAlarmConfiguration"].
    Writes via PUT /v11/video_inputs/{id}/motion {"enabled": true, "motionAlarmConfiguration": value}.
    Disabled by default — enable in Settings → Entities.
    """

    _attr_options = MOTION_SENSITIVITY_OPTIONS
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the motion sensitivity select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry

        cam_data = coordinator.data.get(cam_id, {})
        cam_info = cam_data.get("info", {})
        self._cam_title = cam_info.get("title", cam_id)

        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_sensitivity_select"
        self._attr_translation_key = "motion_sensitivity"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current motion sensitivity level."""
        settings = self.coordinator.motion_settings(self._cam_id)
        val = settings.get("motionAlarmConfiguration")
        if val:
            lower = str(val).lower()
            if lower in MOTION_SENSITIVITY_OPTIONS:
                return lower
            _LOGGER.warning(
                "Unknown motion sensitivity value from API: %s — defaulting to first option",
                val,
            )
            return MOTION_SENSITIVITY_OPTIONS[0]
        return None

    @property
    @override
    def available(self) -> bool:
        """Available only when motion settings have been fetched (slow tier)."""
        return self.coordinator.last_update_success and bool(
            self.coordinator.motion_settings(self._cam_id)
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the new sensitivity level to the camera via cloud API."""
        if option not in MOTION_SENSITIVITY_OPTIONS:
            _LOGGER.warning("Invalid motion sensitivity option: %s", option)
            return
        if _is_gen2_indoor(self) and await _warn_if_privacy_on(
            self, "Motion Sensitivity"
        ):
            return
        api_value = SENSITIVITY_TO_API[option]
        settings = self.coordinator.motion_settings(self._cam_id)
        enabled = settings.get("enabled", True)
        success = await self.coordinator.async_put_camera(
            self._cam_id,
            "motion",
            {"enabled": enabled, "motionAlarmConfiguration": api_value},
        )
        if success:
            motion_data = self.coordinator.data.get(self._cam_id, {}).get("motion", {})
            motion_data["motionAlarmConfiguration"] = api_value
            if self._cam_id in self.coordinator.data:
                self.coordinator.data[self._cam_id]["motion"] = motion_data
            # Write-lock so the slow-tier poll doesn't revert the optimistic
            # value before the cloud catches up.
            self.coordinator.motion_set_at[self._cam_id] = time.monotonic()
            _LOGGER.debug(
                "Motion sensitivity set to %s for %s", api_value, self._cam_id
            )
        else:
            _LOGGER.warning("Failed to set motion sensitivity for %s", self._cam_id)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschFcmPushModeSelect(CoordinatorEntity[BoschCameraCoordinator], SelectEntity):
    """Select entity to choose the FCM push notification mode.

    Options: Auto (FCM push, auto-fallback to polling on registration failure),
    Polling (skip FCM entirely, poll the API instead).
    When changed: restarts FCM with the new mode.
    One per integration (not per camera).
    """

    _attr_options = FCM_PUSH_MODE_OPTIONS
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the FCM push mode select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        self._attr_unique_id = "bosch_shc_camera_fcm_push_mode"
        self._attr_translation_key = "fcm_push_mode"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        cam_title = cam_info.get("title", self._cam_id)
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def available(self) -> bool:
        # Gating: dropdown is wirkungslos solange Master-Switch enable_fcm_push aus ist.
        # Unavailable signalisiert dem User explizit dass erst die Integration-Option
        # gesetzt werden muss, bevor der Push-Mode irgendetwas tut.
        if not super().available:
            return False
        return bool(self.coordinator.options.get("enable_fcm_push", False))

    @property
    @override
    def current_option(self) -> str:
        mode = self._entry.options.get("fcm_push_mode", "auto")  # [S7] direct read
        return mode if mode in FCM_PUSH_MODE_OPTIONS else "auto"

    @override
    async def async_select_option(self, option: str) -> None:
        """Handle push mode selection — update options and restart FCM."""
        # Update the integration options
        new_options = dict(self._entry.options)
        new_options["fcm_push_mode"] = option
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=new_options,
        )
        # Restart FCM with new mode
        await self.coordinator.async_stop_fcm_push()
        self.coordinator.fcm_push_mode = "unknown"
        if self.coordinator.options.get("enable_fcm_push", False):
            # Track the restart task on the coordinator so async_unload_entry can
            # cancel it — an untracked fire-and-forget task could otherwise keep
            # running (and re-establish FCM) after the entry is unloaded/reloaded.
            task = self.hass.async_create_task(self.coordinator.async_start_fcm_push())
            self.coordinator.bg_tasks.add(task)
            task.add_done_callback(self.coordinator.bg_tasks.discard)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschStreamModeSelect(CoordinatorEntity[BoschCameraCoordinator], SelectEntity):
    """Select entity to choose the live stream connection mode.

    Options:
      "Auto (Lokal → Cloud)" — try LOCAL first, fall back to REMOTE cloud proxy
      "Nur Lokal"            — direct LAN only (no internet required)
      "Nur Cloud"            — cloud proxy only (always REMOTE)

    Changes _stream_type_override in-memory — no integration reload needed.
    Takes effect on the next live stream activation.
    One per integration (not per camera).
    """

    _attr_options = STREAM_MODE_OPTIONS
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the stream mode select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        cam_info = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title = cam_info.get("title", cam_id)
        self._attr_unique_id = "bosch_shc_camera_stream_mode"
        self._attr_translation_key = "stream_mode"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str:
        """Return the current stream mode key."""
        mode = self.coordinator.stream_type_override
        if mode is None:
            mode = self._entry.options.get(
                "stream_connection_type", "local"
            )  # [S7] direct read
        return mode if mode in STREAM_MODE_OPTIONS else "local"

    @override
    async def async_select_option(self, option: str) -> None:
        """Handle stream mode selection — update in-memory preference immediately."""
        self.coordinator.stream_type_override = option
        _LOGGER.info("Stream mode set to %s", option)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschDetectionModeSelect(CoordinatorEntity[BoschCameraCoordinator], SelectEntity):
    """Select entity: intrusion detection mode (Gen2 only).

    API values: ALL_MOTIONS / ONLY_HUMANS / ZONES — confirmed via mitm captures
    of the iOS app 2026-04-08 + 2026-04-11.
    Reads from coordinator.intrusion_config_cache[cam_id]["detectionMode"].
    Writes via PUT /v11/video_inputs/{id}/intrusionDetectionConfig.
    """

    _attr_options = DETECTION_MODE_OPTIONS
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the detection mode select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        cam_data = coordinator.data.get(cam_id, {})
        cam_info = cam_data.get("info", {})
        self._cam_title = cam_info.get("title", cam_id)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_detection_mode"
        self._attr_translation_key = "detection_mode"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str | None:
        cfg = self.coordinator.intrusion_config_cache.get(self._cam_id, {})
        val = cfg.get("detectionMode")
        if val:
            lower = str(val).lower()
            if lower in DETECTION_MODE_OPTIONS:
                return lower
            _LOGGER.warning(
                "Unknown detection mode value from API: %s — defaulting to first option",
                val,
            )
            return DETECTION_MODE_OPTIONS[0]
        return None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.intrusion_config_cache.get(self._cam_id)
        )

    @override
    async def async_select_option(self, option: str) -> None:
        if option not in DETECTION_MODE_OPTIONS:
            return
        if await _warn_if_privacy_on(self, "Detection Mode"):
            return
        api_value = DETECTION_TO_API[option]
        cfg = dict(self.coordinator.intrusion_config_cache.get(self._cam_id, {}))
        if not cfg:
            return
        cfg["detectionMode"] = api_value
        success = await self.coordinator.async_put_camera(
            self._cam_id, "intrusionDetectionConfig", cfg
        )
        if success:
            self.coordinator.intrusion_config_cache[self._cam_id] = cfg
            # Stamp the write-lock so the slow-tier poll doesn't revert the UI
            # before the cloud reflects this change (siblings do the same).
            self.coordinator.intrusion_config_set_at[self._cam_id] = time.monotonic()
            _LOGGER.debug(
                "Detection mode set to %s for %s", api_value, self._cam_id[:8]
            )
        else:
            _LOGGER.warning("Failed to set detection mode for %s", self._cam_id[:8])
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschPanPresetSelect(CoordinatorEntity[BoschCameraCoordinator], SelectEntity):
    """Select entity with named PTZ presets for the Gen1 360° indoor camera.

    Options: home (0°), left (-60°), right (+60°), back_left (-120°), back_right (+120°).
    Each selection calls coordinator.async_cloud_set_pan with the mapped angle.
    Only created when featureSupport.panLimit > 0 (CAMERA_360).

    The "current option" is derived live from the coordinator.pan_cache value:
    the closest mapped preset whose angle matches exactly, or None when the
    camera is between presets (e.g. after a manual slider move).
    """

    _attr_options = PAN_PRESET_OPTIONS
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
        pan_limit: int,
    ) -> None:
        """Initialize the pan preset select entity."""
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        self._pan_limit = pan_limit

        cam_data = coordinator.data.get(cam_id, {})
        cam_info = cam_data.get("info", {})
        self._cam_title = cam_info.get("title", cam_id)

        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_pan_preset"
        self._attr_translation_key = "pan_preset"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        cam_data = self.coordinator.data.get(self._cam_id, {})
        cam_info = cam_data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": cam_info.get("hardwareVersion", "Smart Home Camera"),
            "sw_version": cam_info.get("firmwareVersion", ""),
        }

    @property
    @override
    def current_option(self) -> str | None:
        """Return the preset name that matches the current pan position exactly, or None."""
        raw = self.coordinator.pan_cache.get(self._cam_id)
        if raw is None:
            return None
        # Invert sign for ceiling-mounted cameras (mirrors BoschPanNumber logic)
        pos = (
            -int(raw)
            if getattr(self.coordinator, "image_rotation_180", {}).get(self._cam_id)
            else int(raw)
        )
        for name, angle in PAN_PRESET_ANGLES.items():
            if pos == angle:
                return name
        return None

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.pan_cache.get(self._cam_id) is not None
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Move camera to the preset pan angle."""
        if option not in PAN_PRESET_ANGLES:
            _LOGGER.warning("Unknown pan preset: %s", option)
            return
        target_angle = PAN_PRESET_ANGLES[option]
        # Invert sign for ceiling-mounted cameras
        actual = (
            -target_angle
            if getattr(self.coordinator, "image_rotation_180", {}).get(self._cam_id)
            else target_angle
        )
        success = await self.coordinator.async_cloud_set_pan(self._cam_id, actual)
        if success:
            self.coordinator.pan_cache[self._cam_id] = actual
            _LOGGER.debug(
                "Pan preset %s → %d° for %s", option, actual, self._cam_id[:8]
            )
        else:
            _LOGGER.warning(
                "Failed to apply pan preset %s for %s", option, self._cam_id[:8]
            )
        self.async_write_ha_state()
