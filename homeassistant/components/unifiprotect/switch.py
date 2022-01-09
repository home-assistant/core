"""This component provides Switches for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

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
from .models import ProtectRequiredKeysMixin
from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectSwitchEntityDescription(ProtectRequiredKeysMixin, SwitchEntityDescription):
    """Describes UniFi Protect Switch entity."""

    ufp_set_function: str | None = None


_KEY_STATUS_LIGHT = "status_light"
_KEY_HDR_MODE = "hdr_mode"
_KEY_HIGH_FPS = "high_fps"
_KEY_PRIVACY_MODE = "privacy_mode"
_KEY_SYSTEM_SOUNDS = "system_sounds"
_KEY_OSD_NAME = "osd_name"
_KEY_OSD_DATE = "osd_date"
_KEY_OSD_LOGO = "osd_logo"
_KEY_OSD_BITRATE = "osd_bitrate"
_KEY_SMART_PERSON = "smart_person"
_KEY_SMART_VEHICLE = "smart_vehicle"
_KEY_SSH = "ssh"

ALL_DEVICES_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key=_KEY_SSH,
        name="SSH Enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        ufp_value="is_ssh_enabled",
        ufp_set_function="set_ssh",
    ),
)

CAMERA_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key=_KEY_STATUS_LIGHT,
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_led_status",
        ufp_value="led_settings.is_enabled",
        ufp_set_function="set_status_light",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_HDR_MODE,
        name="HDR Mode",
        icon="mdi:brightness-7",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_hdr",
        ufp_value="hdr_mode",
        ufp_set_function="set_hdr",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_HIGH_FPS,
        name="High FPS",
        icon="mdi:video-high-definition",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_highfps",
        ufp_value="video_mode",
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
        key=_KEY_SYSTEM_SOUNDS,
        name="System Sounds",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_set_function="set_system_sounds",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_OSD_NAME,
        name="Overlay: Show Name",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_name_enabled",
        ufp_set_function="set_osd_name",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_OSD_DATE,
        name="Overlay: Show Date",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_date_enabled",
        ufp_set_function="set_osd_date",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_OSD_LOGO,
        name="Overlay: Show Logo",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_logo_enabled",
        ufp_set_function="set_osd_logo",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_OSD_BITRATE,
        name="Overlay: Show Bitrate",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.CONFIG,
        ufp_value="osd_settings.is_debug_enabled",
        ufp_set_function="set_osd_bitrate",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_SMART_PERSON,
        name="Detections: Person",
        icon="mdi:walk",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_value="is_person_detection_on",
        ufp_set_function="set_person_detection",
    ),
    ProtectSwitchEntityDescription(
        key=_KEY_SMART_VEHICLE,
        name="Detections: Vehicle",
        icon="mdi:car",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_value="is_vehicle_detection_on",
        ufp_set_function="set_vehicle_detection",
    ),
)


LIGHT_SWITCHES: tuple[ProtectSwitchEntityDescription, ...] = (
    ProtectSwitchEntityDescription(
        key=_KEY_STATUS_LIGHT,
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        ufp_value="light_device_settings.is_indicator_enabled",
        ufp_set_function="set_status_light",
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
    )
    async_add_entities(entities)


class ProtectSwitch(ProtectDeviceEntity, SwitchEntity):
    """A UniFi Protect Switch."""

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: ProtectSwitchEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect Switch."""
        self.entity_description: ProtectSwitchEntityDescription = description
        super().__init__(data, device)
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
        assert self.entity_description.ufp_value is not None

        ufp_value = get_nested_attr(self.device, self.entity_description.ufp_value)
        if self._switch_type == _KEY_HIGH_FPS:
            return bool(ufp_value == VideoMode.HIGH_FPS)
        return ufp_value is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""

        if self.entity_description.ufp_set_function is not None:
            await getattr(self.device, self.entity_description.ufp_set_function)(True)
            return

        assert isinstance(self.device, Camera)
        if self._switch_type == _KEY_HIGH_FPS:
            _LOGGER.debug("Turning on High FPS mode")
            await self.device.set_video_mode(VideoMode.HIGH_FPS)
            return
        if self._switch_type == _KEY_PRIVACY_MODE:
            _LOGGER.debug("Turning Privacy Mode on for %s", self.device.name)
            self._previous_mic_level = self.device.mic_volume
            self._previous_record_mode = self.device.recording_settings.mode
            await self.device.set_privacy(True, 0, RecordingMode.NEVER)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""

        if self.entity_description.ufp_set_function is not None:
            await getattr(self.device, self.entity_description.ufp_set_function)(False)
            return

        assert isinstance(self.device, Camera)
        if self._switch_type == _KEY_HIGH_FPS:
            _LOGGER.debug("Turning off High FPS mode")
            await self.device.set_video_mode(VideoMode.DEFAULT)
        elif self._switch_type == _KEY_PRIVACY_MODE:
            _LOGGER.debug("Turning Privacy Mode off for %s", self.device.name)
            await self.device.set_privacy(
                False, self._previous_mic_level, self._previous_record_mode
            )
