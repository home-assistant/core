"""Bosch Smart Home Camera — Number Platform.

Creates number entities per camera:
  • {Name} Pan Position     — pan the 360 camera left/right (-120° to +120°).
    Only available for cameras with featureSupport.panLimit > 0 (CAMERA_360).
    Uses cloud API: PUT /v11/video_inputs/{id}/pan
    State is read from GET /v11/video_inputs/{id}/pan (polled each coordinator tick).

  • {Name} Intrusion Sensitivity  — intrusion detection sensitivity 0-7 (Gen2 only).
    Reads from coordinator.intrusion_config_cache[cam_id]["sensitivity"].
    Writes via PUT /v11/video_inputs/{id}/intrusionDetectionConfig — full body preserved.
    FW 9.40+ supports range 0-7 (capture 2026-04-28 confirmed sensitivity=3, max=7).

  • {Name} Intrusion Distance  — detection range in metres 1-8 (Gen2 only).
    Reads from coordinator.intrusion_config_cache[cam_id]["distance"].
    Writes via PUT /v11/video_inputs/{id}/intrusionDetectionConfig — full body preserved.
    API rejects distance > 8 with HTTP 400 (verified FW 9.40.102). Max clamped to 8.
"""

import logging
import time
from typing import Any, override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschCameraConfigEntry
from .base import _BoschEntityBase
from .guards import _get_cam_lock, _is_gen2_indoor, _warn_if_privacy_on
from .models import get_model_config

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch camera number entities for a config entry."""
    coordinator = config_entry.runtime_data
    entities: list[_BoschEntityBase] = []
    for cam_id in coordinator.data:
        cam_info = coordinator.data[cam_id].get("info", {})
        pan_limit = cam_info.get("featureSupport", {}).get("panLimit", 0)
        if pan_limit:
            entities.append(
                BoschPanNumber(coordinator, cam_id, config_entry, pan_limit)
            )
        entities.append(BoschSpeakerLevelNumber(coordinator, cam_id, config_entry))
        # Card playback volume — paired with the audio switch (registered for
        # every camera), the automatable source of truth for the card's volume.
        entities.append(BoschAudioVolumeNumber(coordinator, cam_id, config_entry))
        has_light = cam_info.get("featureSupport", {}).get("light", False)
        if has_light:
            entities.append(
                BoschFrontLightIntensityNumber(coordinator, cam_id, config_entry)
            )
        # Gen2-only entities
        hw = cam_info.get("hardwareVersion", "CAMERA")
        if get_model_config(hw).generation >= 2:
            # lens_elevation works on both Indoor II and Outdoor II
            # (Indoor II slow-tier returns 200 on this endpoint, confirmed 2026-04-11)
            entities.append(BoschLensElevationNumber(coordinator, cam_id, config_entry))
            entities.append(
                BoschMicrophoneLevelNumber(coordinator, cam_id, config_entry)
            )
            # Intrusion detection tuning — available on both Indoor II and Outdoor II.
            entities.append(
                BoschIntrusionSensitivityNumber(coordinator, cam_id, config_entry)
            )
            entities.append(
                BoschIntrusionDistanceNumber(coordinator, cam_id, config_entry)
            )
            # Light-related entities only for cameras that actually expose Gen2 lighting
            # (Indoor II has no RGB/wallwasher lights — only Power-LED via iconLedBrightness).
            if hw not in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
                entities.append(
                    BoschWhiteBalanceNumber(coordinator, cam_id, config_entry)
                )
                entities.append(
                    BoschTopLedBrightnessNumber(coordinator, cam_id, config_entry)
                )
                entities.append(
                    BoschBottomLedBrightnessNumber(coordinator, cam_id, config_entry)
                )
                entities.append(
                    BoschMotionLightSensitivityNumber(coordinator, cam_id, config_entry)
                )
                entities.append(
                    BoschDarknessThresholdNumber(coordinator, cam_id, config_entry)
                )
        # Gen2 Indoor II — alarm delays + power-LED brightness
        if hw in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
            entities.append(
                BoschPowerLedBrightnessNumber(coordinator, cam_id, config_entry)
            )
            entities.append(BoschAlarmDelayNumber(coordinator, cam_id, config_entry))
            entities.append(
                BoschAlarmActivationDelayNumber(coordinator, cam_id, config_entry)
            )
            entities.append(BoschPreAlarmDelayNumber(coordinator, cam_id, config_entry))
    async_add_entities(entities, update_before_add=False)


class BoschPanNumber(_BoschEntityBase, NumberEntity):
    """Number entity to control the pan position of the 360 camera."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: Any, cam_id: str, entry: ConfigEntry, pan_limit: int
    ) -> None:
        """Initialize the pan position number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._pan_limit = pan_limit
        self._attr_unique_id = f"bosch_shc_pan_{cam_id.lower()}"
        self._attr_native_min_value = -pan_limit
        self._attr_native_max_value = pan_limit
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = "°"
        self._attr_translation_key = "pan_position"
        self._attr_entity_category = EntityCategory.CONFIG

    def _rotation_180(self) -> bool:
        """Return True if the camera is configured as ceiling-mounted (image rotated 180°).

        When True, the slider sign is inverted so that "right"
        on the slider stays "right" on the user's screen.
        """
        return bool(
            getattr(self.coordinator, "image_rotation_180", {}).get(self._cam_id)
        )

    @property
    @override
    def native_value(self) -> float | None:
        raw = self.coordinator.pan_cache.get(self._cam_id)
        if raw is None:
            return None
        return float(-raw if self._rotation_180() else raw)

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.pan_cache.get(self._cam_id) is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        # Invert sign when the camera is ceiling-mounted so the user-visible
        # direction matches the camera-physical pan direction.
        actual = -int(value) if self._rotation_180() else int(value)
        await self.coordinator.async_cloud_set_pan(self._cam_id, actual)


# ─────────────────────────────────────────────────────────────────────────────
class BoschSpeakerLevelNumber(_BoschEntityBase, NumberEntity):
    """Number entity to control the intercom speaker volume (0-100).

    Reads from coordinator.audio_cache[cam_id]["speakerLevel"].
    Writes via PUT /v11/video_inputs/{id}/audio with full body preserved —
    same pattern as BoschMicrophoneLevelNumber so audioEnabled is not clobbered.
    Capture 2026-04-08 confirms body shape: {"audioEnabled":true,"microphoneLevel":60,"speakerLevel":80}.
    Disabled by default — enable in Settings -> Entities.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the speaker level number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_speaker_level"
        self._attr_translation_key = "speaker_level"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        """Return speaker level from coordinator audio cache, or None if not yet polled."""
        audio = self.coordinator.audio_cache.get(self._cam_id, {})
        val = audio.get("speakerLevel")
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            self.coordinator.audio_cache.get(self._cam_id) is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the new speaker level to the camera via cloud API.

        Sends full audio body (preserves audioEnabled + microphoneLevel) so
        existing audio settings are not clobbered. Uses async_put_camera for
        consistent token-refresh handling.

        Serialized on a per-camera lock shared with BoschMicrophoneLevelNumber
        and BoschIntercomSwitch (same /audio endpoint, same _audio_cache) so a
        concurrent write to a sibling field can't be clobbered by a stale
        snapshot taken before the lock (bug-hunt 2026-07-03; the merge-only
        -own-field step below already existed since 2026-06-02, but without a
        lock the READ before it could still race).
        """
        level = round(value)
        lock = _get_cam_lock(self.coordinator, "_audio_config_locks", self._cam_id)
        async with lock:
            audio = dict(self.coordinator.audio_cache.get(self._cam_id, {}))
            audio["speakerLevel"] = level
            success = await self.coordinator.async_put_camera(
                self._cam_id, "audio", audio
            )
            if success:
                # Merge only the changed field so a concurrent microphone
                # write isn't clobbered by our stale snapshot.
                self.coordinator.audio_cache.setdefault(self._cam_id, {})[
                    "speakerLevel"
                ] = level
                _LOGGER.debug("Speaker level set to %d for %s", level, self._cam_id)
            else:
                _LOGGER.warning(
                    "Failed to set speaker level for %s: HTTP error", self._cam_id
                )
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschAudioVolumeNumber(_BoschEntityBase, NumberEntity):
    """Card playback volume (0-100 %) for this camera's live audio.

    Virtual preference — there is NO Bosch API for volume (loudness is a browser
    property). This entity is the automatable, cross-session source of truth that
    the Lovelace card applies to its <video> element: the card reads it and writes
    it back via number.set_value, and HA pushes the change to every open card. No
    Bosch write happens here. No effect on iOS (Safari makes video.volume
    read-only). Paired with switch.<cam>_audio (the on/off master).
    """

    DEFAULT_VOLUME = 50

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the audio volume number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_audio_volume_{cam_id.lower()}"
        self._attr_translation_key = "audio_volume"

    @property
    @override
    def native_value(self) -> float:
        return float(
            self.coordinator.audio_volume.get(self._cam_id, self.DEFAULT_VOLUME)
        )

    @property
    @override
    def available(self) -> bool:
        # Grey out together with the camera's other controls when it is offline,
        # rather than staying settable on its own (the audio switch greys too).
        return bool(self.coordinator.last_update_success) and bool(
            self.coordinator.is_camera_online(self._cam_id)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Store the new playback volume — no Bosch API call (browser-side level).

        The card reads this state to set video.volume; HA pushes the change to
        every open card automatically.
        """
        self.coordinator.audio_volume[self._cam_id] = round(value)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschFrontLightIntensityNumber(_BoschEntityBase, NumberEntity):
    """Number entity: front light brightness (0-100%).

    Maps to frontLightIntensity (0.0-1.0) in PUT /v11/video_inputs/{id}/lighting_override.
    Only for cameras with featureSupport.light = True (outdoor cameras).
    Disabled by default — enable in Settings → Entities.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the front light intensity number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_front_light_intensity_{cam_id.lower()}"
        self._attr_translation_key = "front_light_intensity"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        val = self.coordinator.shc_state_cache.get(self._cam_id, {}).get(
            "front_light_intensity"
        )
        if val is not None:
            return float(round(float(val) * 100))
        return None

    @property
    @override
    def available(self) -> bool:
        # Gate on cache presence like the other number entities — otherwise a
        # cache-miss reports "unknown" (available + native_value None) instead of
        # "unavailable", and automations reading the level see an undefined value.
        return bool(self.coordinator.last_update_success) and (
            self.coordinator.shc_state_cache.get(self._cam_id, {}).get(
                "front_light_intensity"
            )
            is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set front light intensity (0-100% → 0.0-1.0 API value)."""
        intensity = round(value / 100, 2)
        success = await self.coordinator.async_cloud_set_light_component(
            self._cam_id, "intensity", intensity
        )
        if not success:
            # The setter (shc.py) never raises — see BoschPrivacyModeSwitch's
            # matching fix (2026-07-07) for why: a total failure across every
            # fallback path used to be invisible (state just reverted).
            _LOGGER.warning(
                "Front light intensity set to %.0f%% failed on all paths for %s "
                "— state unchanged",
                value,
                self._cam_id[:8],
            )


# ─────────────────────────────────────────────────────────────────────────────
class _BoschGen2NumberBase(_BoschEntityBase, NumberEntity):
    """Base class for Gen2-only number entities."""

    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True


class BoschLensElevationNumber(_BoschGen2NumberBase):
    """Number entity: lens mounting height in meters (Gen2 only).

    Reads from GET /v11/video_inputs/{id}/lens_elevation → {"elevation": 2.0}
    Writes via PUT /v11/video_inputs/{id}/lens_elevation → {"elevation": value}
    Used by camera for perspective correction in person detection.
    """

    _attr_native_min_value = 0.5
    _attr_native_max_value = 5.0
    _attr_native_step = 0.05
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "m"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the lens elevation number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_lens_elevation"
        self._attr_translation_key = "lens_elevation"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        val = self.coordinator.lens_elevation_cache.get(self._cam_id)
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return (
            bool(self.coordinator.last_update_success)
            and self.coordinator.lens_elevation_cache.get(self._cam_id) is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        success = await self.coordinator.async_put_camera(
            self._cam_id, "lens_elevation", {"elevation": round(value, 2)}
        )
        if success:
            self.coordinator.lens_elevation_cache[self._cam_id] = value
        self.async_write_ha_state()


class BoschMicrophoneLevelNumber(_BoschGen2NumberBase):
    """Number entity: microphone recording level 0-100% (Gen2 only).

    Reads from GET /v11/video_inputs/{id}/audio → {"microphoneLevel": 60, ...}
    Writes via PUT /v11/video_inputs/{id}/audio → full body with updated microphoneLevel.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the microphone level number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_mic_level"
        self._attr_translation_key = "microphone_level"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        audio = self.coordinator.audio_cache.get(self._cam_id, {})
        val = audio.get("microphoneLevel")
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            self.coordinator.audio_cache.get(self._cam_id) is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        if _is_gen2_indoor(self) and await _warn_if_privacy_on(
            self, "Mikrofon-Lautstärke"
        ):
            return
        level = round(value)
        # Serialized on the same per-camera lock as BoschSpeakerLevelNumber
        # and BoschIntercomSwitch — see that class's docstring (bug-hunt
        # 2026-07-03).
        lock = _get_cam_lock(self.coordinator, "_audio_config_locks", self._cam_id)
        async with lock:
            audio = dict(self.coordinator.audio_cache.get(self._cam_id, {}))
            audio["microphoneLevel"] = level
            success = await self.coordinator.async_put_camera(
                self._cam_id, "audio", audio
            )
            if success:
                # Merge only the changed field (see speaker-level note).
                self.coordinator.audio_cache.setdefault(self._cam_id, {})[
                    "microphoneLevel"
                ] = level
        self.async_write_ha_state()


_LIGHT_SW_DEFAULT: dict[str, Any] = {
    "brightness": 0,
    "color": None,
    "whiteBalance": 0.0,
}


def _lighting_switch_body(cached: dict[str, Any]) -> dict[str, Any]:
    """Build full lighting/switch PUT body from cache (API requires all 3 groups)."""
    return {
        k: cached.get(k, _LIGHT_SW_DEFAULT)
        for k in ("frontLightSettings", "topLedLightSettings", "bottomLedLightSettings")
    }


class BoschWhiteBalanceNumber(_BoschGen2NumberBase):
    """Number entity: front light color temperature -1.0 to 1.0 (Gen2 only).

    -1.0 = cool/blue, 0.0 = neutral, 1.0 = warm/orange.
    Only applies to front light (top/bottom LEDs use RGB color instead).
    Reads from GET /v11/video_inputs/{id}/lighting/switch → frontLightSettings.whiteBalance
    Writes via PUT /lighting/switch with frontLightSettings only.
    """

    _attr_native_min_value = -1.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.05
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the white balance number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_white_balance"
        self._wb_value: float | None = None
        self._attr_translation_key = "white_balance"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        cached = self.coordinator.lighting_switch_cache.get(self._cam_id, {})
        front = cached.get("frontLightSettings", {})
        wb = front.get("whiteBalance")
        if wb is not None:
            self._wb_value = wb
        return self._wb_value

    @property
    @override
    def available(self) -> bool:
        # Gate on the lighting cache being populated — a write during the
        # pre-populate / failed-sub-fetch window would PUT zero-defaults and
        # clobber the camera's real light settings (bug-hunt 2026-06-02).
        return bool(self.coordinator.last_update_success) and (
            self.coordinator.lighting_switch_cache.get(self._cam_id, {}).get(
                "frontLightSettings"
            )
            is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set white balance for front light — sends FULL body (API requirement)."""
        wb = round(value, 2)
        cached = self.coordinator.lighting_switch_cache.get(self._cam_id, {})
        body = _lighting_switch_body(cached)
        body["frontLightSettings"] = {
            **body["frontLightSettings"],
            "whiteBalance": wb,
            "color": None,
        }
        # Route through the coordinator's universal writer, which handles a 401
        # via token-refresh + retry. Previously this used a raw Bearer PUT that
        # silently failed on an expired token (bug-hunt 2026-06-02).
        ok = await self.coordinator.async_put_camera(
            self._cam_id, "lighting/switch", body
        )
        if ok:
            self._wb_value = wb
            # Merge ONLY the group we changed into the live cache (not the whole
            # snapshot) so a concurrent sibling write to a different light group
            # isn't clobbered by our stale snapshot (bug-hunt 2026-06-02).
            cur = self.coordinator.lighting_switch_cache.setdefault(self._cam_id, {})
            cur["frontLightSettings"] = body["frontLightSettings"]
            _LOGGER.debug("White balance set to %.2f for %s", wb, self._cam_id[:8])
        else:
            _LOGGER.warning("White balance write failed for %s", self._cam_id[:8])
        self.async_write_ha_state()


class _BoschLedBrightnessBase(_BoschGen2NumberBase):
    """Base for Top/Bottom LED brightness (0-100%, Gen2 only)."""

    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _led_key: str = ""  # override in subclass
    _brightness: float | None  # declared here so mypy sees it before property use

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the LED brightness number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._brightness = None

    @property
    @override
    def native_value(self) -> float | None:
        cached = self.coordinator.lighting_switch_cache.get(self._cam_id, {})
        led = cached.get(self._led_key, {})
        val = led.get("brightness")
        if val is not None:
            self._brightness = float(val)
        return self._brightness

    @property
    @override
    def available(self) -> bool:
        # Gate on the lighting cache (see white-balance note) — avoids writing
        # zero-defaults that clobber real settings before the cache is populated.
        return bool(self.coordinator.last_update_success) and (
            self.coordinator.lighting_switch_cache.get(self._cam_id, {}).get(
                self._led_key
            )
            is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set brightness — sends FULL body with all 3 groups (API requirement)."""
        brightness = round(value)
        cached = self.coordinator.lighting_switch_cache.get(self._cam_id, {})
        body = _lighting_switch_body(cached)
        body[self._led_key] = {**body[self._led_key], "brightness": brightness}
        # Route through the coordinator's universal writer (401 → token-refresh
        # + retry) instead of a raw Bearer PUT that silently failed on an
        # expired token (bug-hunt 2026-06-02).
        ok = await self.coordinator.async_put_camera(
            self._cam_id, "lighting/switch", body
        )
        if ok:
            self._brightness = float(brightness)
            # Merge only the changed LED group (see white-balance note above).
            cur = self.coordinator.lighting_switch_cache.setdefault(self._cam_id, {})
            cur[self._led_key] = body[self._led_key]
            _LOGGER.debug(
                "%s brightness set to %d for %s",
                self._led_key,
                brightness,
                self._cam_id[:8],
            )
        else:
            _LOGGER.warning(
                "%s brightness write failed for %s",
                self._led_key,
                self._cam_id[:8],
            )
        self.async_write_ha_state()


class BoschTopLedBrightnessNumber(_BoschLedBrightnessBase):
    """Number entity: top LED brightness 0-100% (Gen2, oberes Licht)."""

    _led_key = "topLedLightSettings"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the top LED brightness number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_top_led_brightness"
        self._attr_translation_key = "top_led_brightness"
        self._attr_entity_category = EntityCategory.CONFIG


class BoschBottomLedBrightnessNumber(_BoschLedBrightnessBase):
    """Number entity: bottom LED brightness 0-100% (Gen2, unteres Licht)."""

    _led_key = "bottomLedLightSettings"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the bottom LED brightness number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_bottom_led_brightness"
        self._attr_translation_key = "bottom_led_brightness"
        self._attr_entity_category = EntityCategory.CONFIG


class BoschMotionLightSensitivityNumber(_BoschGen2NumberBase):
    """Number entity: motion-triggered light sensitivity 1-5 (Gen2 only).

    Reads from GET /v11/video_inputs/{id}/lighting/motion → motionLightSensitivity
    Writes via PUT /v11/video_inputs/{id}/lighting/motion with full body.
    1 = low sensitivity, 5 = high sensitivity.
    """

    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the motion light sensitivity number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_light_sensitivity"
        self._attr_translation_key = "motion_light_sensitivity"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        cache = self.coordinator.motion_light_cache.get(self._cam_id, {})
        val = cache.get("motionLightSensitivity")
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.motion_light_cache.get(self._cam_id)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        cache = dict(self.coordinator.motion_light_cache.get(self._cam_id, {}))
        if not cache:
            return
        cache["motionLightSensitivity"] = round(value)
        success = await self.coordinator.async_put_camera(
            self._cam_id, "lighting/motion", cache
        )
        if success:
            self.coordinator.motion_light_cache[self._cam_id] = cache
        self.async_write_ha_state()


class BoschDarknessThresholdNumber(_BoschGen2NumberBase):
    """Number entity: darkness threshold 0-100% (Gen2 only).

    Controls when the camera switches from day to night lighting mode.
    0 = always day, 100 = always night.
    Reads from GET /v11/video_inputs/{id}/lighting → {"darknessThreshold": 0.47, "softLightFading": bool}
    Writes via PUT /v11/video_inputs/{id}/lighting with full body.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the darkness threshold number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_darkness_threshold"
        self._attr_translation_key = "darkness_threshold"

    @property
    @override
    def native_value(self) -> float | None:
        cache = self.coordinator.global_lighting_cache.get(self._cam_id, {})
        val = cache.get("darknessThreshold")
        return round(float(val) * 100, 0) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.global_lighting_cache.get(self._cam_id)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        cache = self.coordinator.global_lighting_cache.get(self._cam_id, {})
        soft_fading = cache.get("softLightFading", True)
        body = {
            "darknessThreshold": round(value / 100, 4),
            "softLightFading": soft_fading,
        }
        success = await self.coordinator.async_put_camera(
            self._cam_id, "lighting", body
        )
        if success:
            self.coordinator.global_lighting_cache[self._cam_id] = body
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
# Gen2 Indoor II — Power-LED brightness + Alarm delays + Audio alarm sensitivity
# ─────────────────────────────────────────────────────────────────────────────
class BoschPowerLedBrightnessNumber(_BoschGen2NumberBase):
    """Number: Power-LED brightness (0-4, 5 discrete steps) — white LED showing camera is powered.

    Maps to "Power-LED" slider in iOS app → Kamera-Funktionen.
    Distinct from Status-LED (red, recording indicator, BoschStatusLedSwitch).
    PUT /v11/video_inputs/{id}/iconLedBrightness  body: {"value": 0-4}
    Confirmed by direct API test 2026-04-11: writing value=5 → HTTP 400
    "must be less than or equal to 4". The iOS app shows this as a percent
    slider but internally maps to 5 discrete positions (0 = off, 4 = max).
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 4
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the power-LED brightness number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_power_led_brightness"
        self._attr_translation_key = "power_led_brightness"

    @property
    @override
    def native_value(self) -> float | None:
        val = self.coordinator.icon_led_brightness_cache.get(self._cam_id)
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return (
            bool(self.coordinator.last_update_success)
            and self.coordinator.icon_led_brightness_cache.get(self._cam_id) is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        val = round(max(0, min(4, value)))
        success = await self.coordinator.async_put_camera(
            self._cam_id, "iconLedBrightness", {"value": val}
        )
        if success:
            self.coordinator.icon_led_brightness_cache[self._cam_id] = val
        self.async_write_ha_state()


class _BoschAlarmDelayBase(_BoschGen2NumberBase):
    """Shared base for alarm_settings integer fields."""

    _field: str = ""
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "s"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def _settings(self) -> dict[str, Any]:
        return self.coordinator.alarm_settings_cache.get(self._cam_id, {})

    @property
    @override
    def native_value(self) -> float | None:
        val = self._settings.get(self._field)
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self._settings)

    @override
    async def async_set_native_value(self, value: float) -> None:
        cfg = dict(self._settings)
        if not cfg:
            return
        # Privacy mode blocks /alarm_settings PUT with HTTP 443 on Gen2 Indoor cameras.
        # Without this guard the write silently fails — the cache isn't updated, so
        # native_value re-reads the old value and HA's verify-timeout fires.
        if _is_gen2_indoor(self) and await _warn_if_privacy_on(self, "Alarm Settings"):
            return
        cfg[self._field] = round(value)
        success = await self.coordinator.async_put_camera(
            self._cam_id, "alarm_settings", cfg
        )
        if success:
            self.coordinator.alarm_settings_cache[self._cam_id] = cfg
            # Write-lock so the slow-tier poll doesn't revert this before the
            # cloud reflects it (mirrors the intrusion-config pattern).
            self.coordinator.alarm_settings_set_at[self._cam_id] = time.monotonic()
        self.async_write_ha_state()


class BoschAlarmDelayNumber(_BoschAlarmDelayBase):
    """Number: siren duration (alarm_settings.alarmDelayInSeconds).

    How long the 75 dB siren stays active when triggered.
    Observed range from capture: 52-76s.
    """

    _field = "alarmDelayInSeconds"
    _attr_native_min_value = 10
    _attr_native_max_value = 300

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the alarm delay number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_delay"
        self._attr_translation_key = "alarm_delay"


class BoschAlarmActivationDelayNumber(_BoschAlarmDelayBase):
    """Number: siren activation delay (alarm_settings.alarmActivationDelaySeconds).

    Time between detection and siren activation. Observed: 1-180s.
    """

    _field = "alarmActivationDelaySeconds"
    _attr_native_min_value = 0
    _attr_native_max_value = 600

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the alarm activation delay number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_activation_delay"
        self._attr_translation_key = "alarm_activation_delay"


class BoschPreAlarmDelayNumber(_BoschAlarmDelayBase):
    """Number: pre-alarm duration (alarm_settings.preAlarmDelayInSeconds).

    How long the LED warning stays active before the siren fires.
    Observed: 30-38s.
    """

    _field = "preAlarmDelayInSeconds"
    _attr_native_min_value = 0
    _attr_native_max_value = 300

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the pre-alarm delay number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_prealarm_delay"
        self._attr_translation_key = "pre_alarm_delay"


# ─────────────────────────────────────────────────────────────────────────────
# Gen2 — Intrusion Detection Number Entities
# ─────────────────────────────────────────────────────────────────────────────


class BoschIntrusionSensitivityNumber(_BoschGen2NumberBase):
    """Number: intrusion detection sensitivity 0-7 (Gen2 only).

    FW 9.40+ raised the range from 0-5 to 0-7 (confirmed via captures 2026-04-28:
    value=3 seen, comment in api-findings.md §5 "sensitivity bis 7 (vorher 5)").
    Reads from coordinator.intrusion_config_cache[cam_id]["sensitivity"].
    Writes via PUT /v11/video_inputs/{id}/intrusionDetectionConfig — full body is
    preserved from cache so detectionMode / distance / enabled are not clobbered.
    Write-lock timestamp _intrusion_config_set_at is set after successful PUT to
    prevent slow-tier poll from reverting the optimistic cache update.
    Available for both Gen2 Indoor II (HOME_Eyes_Indoor) and Gen2 Outdoor II
    (HOME_Eyes_Outdoor) — intrusion detection is present on both hardware variants.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 7
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the intrusion sensitivity number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_intrusion_sensitivity"
        self._attr_translation_key = "intrusion_sensitivity"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        cfg = self.coordinator.intrusion_config_cache.get(self._cam_id, {})
        val = cfg.get("sensitivity")
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.intrusion_config_cache.get(self._cam_id)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        cfg = dict(self.coordinator.intrusion_config_cache.get(self._cam_id, {}))
        if not cfg:
            return
        cfg["sensitivity"] = round(max(0, min(7, value)))
        success = await self.coordinator.async_put_camera(
            self._cam_id, "intrusionDetectionConfig", cfg
        )
        if success:
            self.coordinator.intrusion_config_cache[self._cam_id] = cfg
            self.coordinator.intrusion_config_set_at[self._cam_id] = time.monotonic()
            _LOGGER.debug(
                "Intrusion sensitivity set to %d for %s",
                cfg["sensitivity"],
                self._cam_id[:8],
            )
        else:
            _LOGGER.warning(
                "Failed to set intrusion sensitivity for %s", self._cam_id[:8]
            )
        self.async_write_ha_state()


class BoschIntrusionDistanceNumber(_BoschGen2NumberBase):
    """Number: intrusion detection range in metres 1-8 (Gen2 only).

    Reads from coordinator.intrusion_config_cache[cam_id]["distance"].
    Writes via PUT /v11/video_inputs/{id}/intrusionDetectionConfig — full body preserved.
    Range: API rejects distance > 8 with HTTP 400 (verified live FW 9.40.102 2026-05-29).
    Available for both Gen2 Indoor II and Gen2 Outdoor II.
    Write-lock timestamp _intrusion_config_set_at is set after successful PUT (same guard
    as BoschIntrusionSensitivityNumber and BoschDetectionModeSelect).
    """

    _attr_native_min_value = 1
    _attr_native_max_value = 8
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "m"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the intrusion distance number entity."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_intrusion_distance"
        self._attr_translation_key = "intrusion_distance"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def native_value(self) -> float | None:
        cfg = self.coordinator.intrusion_config_cache.get(self._cam_id, {})
        val = cfg.get("distance")
        return float(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(
            self.coordinator.intrusion_config_cache.get(self._cam_id)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        cfg = dict(self.coordinator.intrusion_config_cache.get(self._cam_id, {}))
        if not cfg:
            return
        cfg["distance"] = round(max(1, min(8, value)))  # API rejects > 8 (HTTP 400)
        success = await self.coordinator.async_put_camera(
            self._cam_id, "intrusionDetectionConfig", cfg
        )
        if success:
            self.coordinator.intrusion_config_cache[self._cam_id] = cfg
            self.coordinator.intrusion_config_set_at[self._cam_id] = time.monotonic()
            _LOGGER.debug(
                "Intrusion distance set to %d m for %s",
                cfg["distance"],
                self._cam_id[:8],
            )
        else:
            _LOGGER.warning("Failed to set intrusion distance for %s", self._cam_id[:8])
        self.async_write_ha_state()
