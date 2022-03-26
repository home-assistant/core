"""This component provides Switches for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Generic

from pyunifiprotect.data import Camera, RecordingMode, VideoMode
from pyunifiprotect.data.base import ProtectAdoptableDeviceModel

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import ProtectSetableKeysMixin, T

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectSwitchEntityDescription(
    ProtectSetableKeysMixin, SwitchEntityDescription, Generic[T]
):
    """Describes UniFi Protect Switch entity."""


_KEY_PRIVACY_MODE = "privacy_mode"


def _get_is_highfps(obj: Camera) -> bool:
    return bool(obj.video_mode == VideoMode.HIGH_FPS)


async def _set_highfps(obj: Camera, value: bool) -> None:
    if value:
        await obj.set_video_mode(VideoMode.HIGH_FPS)
    else:
        await obj.set_video_mode(VideoMode.DEFAULT)


ALL_DEVICES_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="ssh",
        name="SSH Enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_ssh_enabled",
        ufp_set_method="set_ssh",
    ),
)

CAMERA_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_led_status",
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
    ),
    ProtectSwitchEntityDescription(
        key="hdr_mode",
        name="HDR Mode",
        icon="mdi:brightness-7",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_hdr",
        ufp_value="hdr_mode",
        ufp_set_method="set_hdr",
    ),
    ProtectSwitchEntityDescription[Camera](
        key="high_fps",
        name="High FPS",
        icon="mdi:video-high-definition",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_highfps",
        ufp_value_fn=_get_is_highfps,
        ufp_set_method_fn=_set_highfps,
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_PRIVACY_MODE,
        name="Privacy Mode",
        icon="mdi:eye-settings",
        entity_category=None,
        ufp_required_field="feature_flags.has_privacy_mask",
        ufp_value="is_privacy_on",
    ),
    ProtectSwitchEntityDescription(
        key="system_sounds",
        name="System Sounds",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_set_method="set_system_sounds",
    ),
    ProtectSwitchEntityDescription(
        key="osd_name",
        name="Overlay: Show Name",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_name_enabled",
        ufp_set_method="set_osd_name",
    ),
    ProtectSwitchEntityDescription(
        key="osd_date",
        name="Overlay: Show Date",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_date_enabled",
        ufp_set_method="set_osd_date",
    ),
    ProtectSwitchEntityDescription(
        key="osd_logo",
        name="Overlay: Show Logo",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_logo_enabled",
        ufp_set_method="set_osd_logo",
    ),
    ProtectSwitchEntityDescription(
        key="osd_bitrate",
        name="Overlay: Show Bitrate",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_debug_enabled",
        ufp_set_method="set_osd_bitrate",
    ),
    ProtectSwitchEntityDescription(
        key="smart_person",
        name="Detections: Person",
        icon="mdi:walk",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_value="is_person_detection_on",
        ufp_set_method="set_person_detection",
    ),
    ProtectSwitchEntityDescription(
        key="smart_vehicle",
        name="Detections: Vehicle",
        icon="mdi:car",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_value="is_vehicle_detection_on",
        ufp_set_method="set_vehicle_detection",
    ),
)

SENSE_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
    ),
    ProtectSwitchEntityDescription(
        key="motion",
        name="Motion Detection",
        icon="mdi:walk",
        entity_category=EntityCategory.CONFIG,
        ufp_value="motion_settings.is_enabled",
        ufp_set_method="set_motion_status",
    ),
    ProtectSwitchEntityDescription(
        key="temperature",
        name="Temperature Sensor",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        ufp_value="temperature_settings.is_enabled",
        ufp_set_method="set_temperature_status",
    ),
    ProtectSwitchEntityDescription(
        key="humidity",
        name="Humidity Sensor",
        icon="mdi:water-percent",
        entity_category=EntityCategory.CONFIG,
        ufp_value="humidity_settings.is_enabled",
        ufp_set_method="set_humidity_status",
    ),
    ProtectSwitchEntityDescription(
        key="light",
        name="Light Sensor",
        icon="mdi:brightness-5",
        entity_category=EntityCategory.CONFIG,
        ufp_value="light_settings.is_enabled",
        ufp_set_method="set_light_status",
    ),
    ProtectSwitchEntityDescription(
        key="alarm",
        name="Alarm Sound Detection",
        entity_category=EntityCategory.CONFIG,
        ufp_value="alarm_settings.is_enabled",
        ufp_set_method="set_alarm_status",
    ),
)


LIGHT_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_value="light_device_settings.is_indicator_enabled",
        ufp_set_method="set_status_light",
    ),
)

DOORLOCK_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_value="led_settings.is_enabled",
        ufp_set_method="set_status_light",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectSwitch,
        all_descs=ALL_DEVICES_SWITCHES,
        camera_descs=CAMERA_SWITCHES,
        light_descs=LIGHT_SWITCHES,
        sense_descs=SENSE_SWITCHES,
        lock_descs=DOORLOCK_SWITCHES,
    )
    async_add_entities(entities)


class ProtectSwitch(ProtectDeviceEntity, SwitchEntity):
    """A UniFi Protect Switch."""

    entity_description: ProtectSwitchEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: ProtectSwitchEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect Switch."""
        super().__init__(data, device, description)
        self._attr_name = f"{self.device.name} {self.entity_description.name}"
        self._switch_type = self.entity_description.key

        if not isinstance(self.device, Camera):
            return

        if self.entity_description.key == _KEY_PRIVACY_MODE:
            if self.device.is_privacy_on:
                self._previous_mic_level = 100
                self._previous_record_mode = RecordingMode.ALWAYS
            else:
                self._previous_mic_level = self.device.mic_volume
                self._previous_record_mode = self.device.recording_settings.mode

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.get_ufp_value(self.device) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._switch_type == _KEY_PRIVACY_MODE:
            assert isinstance(self.device, Camera)
            self._previous_mic_level = self.device.mic_volume
            self._previous_record_mode = self.device.recording_settings.mode
            await self.device.set_privacy(True, 0, RecordingMode.NEVER)
        else:
            await self.entity_description.ufp_set(self.device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""

        if self._switch_type == _KEY_PRIVACY_MODE:
            assert isinstance(self.device, Camera)
            _LOGGER.debug("Setting Privacy Mode to false for %s", self.device.name)
            await self.device.set_privacy(
                False, self._previous_mic_level, self._previous_record_mode
            )
        else:
            await self.entity_description.ufp_set(self.device, False)
