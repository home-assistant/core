"""Component providing Switches for UniFi Protect."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

from uiprotect.data import (
    Camera,
    ModelType,
    ProtectAdoptableDeviceModel,
    RecordingMode,
    VideoMode,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    BaseProtectEntity,
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectIsOnEntity,
    ProtectNVREntity,
    ProtectSettableKeysMixin,
    T,
    async_all_device_entities,
)
from .utils import async_ufp_instance_command

ATTR_PREV_MIC = "prev_mic_level"
ATTR_PREV_RECORD = "prev_record_mode"
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ProtectSwitchEntityDescription(
    ProtectSettableKeysMixin[T], SwitchEntityDescription
):
    """Describes UniFi Protect Switch entity."""


async def _set_highfps(obj: Camera, value: bool) -> None:
    await obj.set_video_mode(VideoMode.HIGH_FPS if value else VideoMode.DEFAULT)


CAMERA_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="ssh",
        translation_key="ssh_enabled",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_ssh_enabled",
        ufp_set_method="set_ssh",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="status_light",
        translation_key="status_light",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_led_status",
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="hdr_mode",
        translation_key="hdr_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        ufp_required_field="feature_flags.has_hdr",
        ufp_value="hdr_mode",
        ufp_set_method="set_hdr",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription[Camera](
        key="high_fps",
        translation_key="high_fps",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_highfps",
        ufp_value="is_high_fps_enabled",
        ufp_set_method_fn=_set_highfps,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="system_sounds",
        translation_key="system_sounds",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_enabled="feature_flags.has_speaker",
        ufp_set_method="set_system_sounds",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="osd_name",
        translation_key="overlay_show_name",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_name_enabled",
        ufp_set_method="set_osd_name",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="osd_date",
        translation_key="overlay_show_date",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_date_enabled",
        ufp_set_method="set_osd_date",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="osd_logo",
        translation_key="overlay_show_logo",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_logo_enabled",
        ufp_set_method="set_osd_logo",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="osd_bitrate",
        translation_key="overlay_show_nerd_mode",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_debug_enabled",
        ufp_set_method="set_osd_bitrate",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="color_night_vision",
        translation_key="color_night_vision",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="has_color_night_vision",
        ufp_value="isp_settings.is_color_night_vision_enabled",
        ufp_set_method="set_color_night_vision",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="motion",
        translation_key="motion",
        entity_category=EntityCategory.CONFIG,
        ufp_value="recording_settings.enable_motion_detection",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_motion_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_person",
        translation_key="detections_person",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_person",
        ufp_value="is_person_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_person_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_vehicle",
        translation_key="detections_vehicle",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_vehicle",
        ufp_value="is_vehicle_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_vehicle_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_animal",
        translation_key="detections_animal",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_animal",
        ufp_value="is_animal_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_animal_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_package",
        translation_key="detections_package",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_package",
        ufp_value="is_package_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_package_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_licenseplate",
        translation_key="detections_license_plate",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_license_plate",
        ufp_value="is_license_plate_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_license_plate_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_smoke",
        translation_key="detections_smoke",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_smoke",
        ufp_value="is_smoke_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_smoke_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_cmonx",
        translation_key="detections_co_alarm",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_co",
        ufp_value="is_co_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_cmonx_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_siren",
        translation_key="detections_siren",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_siren",
        ufp_value="is_siren_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_siren_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_baby_cry",
        translation_key="detections_baby_cry",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_baby_cry",
        ufp_value="is_baby_cry_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_baby_cry_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_speak",
        translation_key="detections_speak",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_speaking",
        ufp_value="is_speaking_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_speaking_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_bark",
        translation_key="detections_bark",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_bark",
        ufp_value="is_bark_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_bark_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_car_alarm",
        translation_key="detections_car_alarm",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_car_alarm",
        ufp_value="is_car_alarm_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_car_alarm_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_car_horn",
        translation_key="detections_car_horn",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_car_horn",
        ufp_value="is_car_horn_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_car_horn_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="smart_glass_break",
        translation_key="detections_glass_break",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="can_detect_glass_break",
        ufp_value="is_glass_break_detection_on",
        ufp_enabled="is_recording_enabled",
        ufp_set_method="set_glass_break_detection",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="track_person",
        translation_key="tracking_person",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.is_ptz",
        ufp_value="is_person_tracking_enabled",
        ufp_set_method="set_person_track",
        ufp_perm=PermRequired.WRITE,
    ),
)

PRIVACY_MODE_SWITCH = ProtectSwitchEntityDescription[Camera](
    key="privacy_mode",
    translation_key="privacy_mode",
    entity_category=EntityCategory.CONFIG,
    ufp_required_field="feature_flags.has_privacy_mask",
    ufp_value="is_privacy_on",
    ufp_perm=PermRequired.WRITE,
)

SENSE_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        translation_key="status_light",
        entity_category=EntityCategory.CONFIG,
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="motion",
        translation_key="detections_motion",
        entity_category=EntityCategory.CONFIG,
        ufp_value="motion_settings.is_enabled",
        ufp_set_method="set_motion_status",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="temperature",
        translation_key="temperature_sensor",
        entity_category=EntityCategory.CONFIG,
        ufp_value="temperature_settings.is_enabled",
        ufp_set_method="set_temperature_status",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="humidity",
        translation_key="humidity_sensor",
        entity_category=EntityCategory.CONFIG,
        ufp_value="humidity_settings.is_enabled",
        ufp_set_method="set_humidity_status",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="light",
        translation_key="light_sensor",
        entity_category=EntityCategory.CONFIG,
        ufp_value="light_settings.is_enabled",
        ufp_set_method="set_light_status",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="alarm",
        translation_key="alarm_sound_detection",
        entity_category=EntityCategory.CONFIG,
        ufp_value="alarm_settings.is_enabled",
        ufp_set_method="set_alarm_status",
        ufp_perm=PermRequired.WRITE,
    ),
)


LIGHT_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="ssh",
        translation_key="ssh_enabled",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_ssh_enabled",
        ufp_set_method="set_ssh",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSwitchEntityDescription(
        key="status_light",
        translation_key="status_light",
        entity_category=EntityCategory.CONFIG,
        ufp_value="light_device_settings.is_indicator_enabled",
        ufp_set_method="set_status_light",
        ufp_perm=PermRequired.WRITE,
    ),
)

DOORLOCK_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        translation_key="status_light",
        entity_category=EntityCategory.CONFIG,
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
        ufp_perm=PermRequired.WRITE,
    ),
)

VIEWER_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="ssh",
        translation_key="ssh_enabled",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_ssh_enabled",
        ufp_set_method="set_ssh",
        ufp_perm=PermRequired.WRITE,
    ),
)

NVR_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="analytics_enabled",
        translation_key="analytics_enabled",
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_analytics_enabled",
        ufp_set_method="set_anonymous_analytics",
    ),
    ProtectSwitchEntityDescription(
        key="insights_enabled",
        translation_key="insights_enabled",
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_insights_enabled",
        ufp_set_method="set_insights",
    ),
)

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_SWITCHES,
    ModelType.LIGHT: LIGHT_SWITCHES,
    ModelType.SENSOR: SENSE_SWITCHES,
    ModelType.DOORLOCK: DOORLOCK_SWITCHES,
    ModelType.VIEWPORT: VIEWER_SWITCHES,
}

_PRIVACY_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: [PRIVACY_MODE_SWITCH]
}


class ProtectBaseSwitch(ProtectIsOnEntity):
    """Base class for UniFi Protect Switch."""

    entity_description: ProtectSwitchEntityDescription

    @async_ufp_instance_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.entity_description.ufp_set(self.device, True)

    @async_ufp_instance_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.entity_description.ufp_set(self.device, False)


class ProtectSwitch(ProtectDeviceEntity, ProtectBaseSwitch, SwitchEntity):
    """A UniFi Protect Switch."""

    entity_description: ProtectSwitchEntityDescription


class ProtectNVRSwitch(ProtectNVREntity, ProtectBaseSwitch, SwitchEntity):
    """A UniFi Protect NVR Switch."""

    entity_description: ProtectSwitchEntityDescription


class ProtectPrivacyModeSwitch(RestoreEntity, ProtectSwitch):
    """A UniFi Protect Switch."""

    device: Camera
    entity_description: ProtectSwitchEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: Camera,
        description: ProtectSwitchEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect Switch."""
        super().__init__(data, device, description)
        if device.is_privacy_on:
            extra_state = self.extra_state_attributes or {}
            self._previous_mic_level = extra_state.get(ATTR_PREV_MIC, 100)
            self._previous_record_mode = extra_state.get(
                ATTR_PREV_RECORD, RecordingMode.ALWAYS
            )
        else:
            self._previous_mic_level = device.mic_volume
            self._previous_record_mode = device.recording_settings.mode

    @callback
    def _update_previous_attr(self) -> None:
        if self.is_on:
            self._attr_extra_state_attributes = {
                ATTR_PREV_MIC: self._previous_mic_level,
                ATTR_PREV_RECORD: self._previous_record_mode,
            }
        else:
            self._attr_extra_state_attributes = {}

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        # do not add extra state attribute on initialize
        if self.entity_id:
            self._update_previous_attr()

    @async_ufp_instance_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._previous_mic_level = self.device.mic_volume
        self._previous_record_mode = self.device.recording_settings.mode
        await self.device.set_privacy(True, 0, RecordingMode.NEVER)

    @async_ufp_instance_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        extra_state = self.extra_state_attributes or {}
        prev_mic = extra_state.get(ATTR_PREV_MIC, self._previous_mic_level)
        prev_record = extra_state.get(ATTR_PREV_RECORD, self._previous_record_mode)
        await self.device.set_privacy(False, prev_mic, prev_record)

    async def async_added_to_hass(self) -> None:
        """Restore extra state attributes on startup."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        last_attrs = last_state.attributes
        self._previous_mic_level = last_attrs.get(
            ATTR_PREV_MIC, self._previous_mic_level
        )
        self._previous_record_mode = last_attrs.get(
            ATTR_PREV_RECORD, self._previous_record_mode
        )
        self._update_previous_attr()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        _make_entities = partial(async_all_device_entities, data, ufp_device=device)
        entities: list[BaseProtectEntity] = []
        entities += _make_entities(ProtectSwitch, _MODEL_DESCRIPTIONS)
        entities += _make_entities(ProtectPrivacyModeSwitch, _PRIVACY_DESCRIPTIONS)
        async_add_entities(entities)

    _make_entities = partial(async_all_device_entities, data)
    data.async_subscribe_adopt(_add_new_device)
    entities: list[BaseProtectEntity] = []
    entities += _make_entities(ProtectSwitch, _MODEL_DESCRIPTIONS)
    entities += _make_entities(ProtectPrivacyModeSwitch, _PRIVACY_DESCRIPTIONS)
    bootstrap = data.api.bootstrap
    nvr = bootstrap.nvr
    if nvr.can_write(bootstrap.auth_user) and nvr.is_insights_enabled is not None:
        entities.extend(
            ProtectNVRSwitch(data, device=nvr, description=switch)
            for switch in NVR_SWITCHES
        )
    async_add_entities(entities)
