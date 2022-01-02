"""This component provides number entities for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyunifiprotect.data.devices import Camera, Light

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import ProtectRequiredKeysMixin
from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)

_KEY_WDR = "wdr_value"
_KEY_MIC_LEVEL = "mic_level"
_KEY_ZOOM_POS = "zoom_position"
_KEY_SENSITIVITY = "sensitivity"
_KEY_DURATION = "duration"
_KEY_CHIME = "chime_duration"


@dataclass
class NumberKeysMixin:
    """Mixin for required keys."""

    ufp_max: int
    ufp_min: int
    ufp_step: int
    ufp_set_function: str


@dataclass
class ProtectNumberEntityDescription(
    ProtectRequiredKeysMixin, NumberEntityDescription, NumberKeysMixin
):
    """Describes UniFi Protect Number entity."""


CAMERA_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key=_KEY_WDR,
        name="Wide Dynamic Range",
        icon="mdi:state-machine",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=3,
        ufp_step=1,
        ufp_required_field="feature_flags.has_wdr",
        ufp_value="isp_settings.wdr",
        ufp_set_function="set_wdr_level",
    ),
    ProtectNumberEntityDescription(
        key=_KEY_MIC_LEVEL,
        name="Microphone Level",
        icon="mdi:microphone",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="feature_flags.has_mic",
        ufp_value="mic_volume",
        ufp_set_function="set_mic_volume",
    ),
    ProtectNumberEntityDescription(
        key=_KEY_ZOOM_POS,
        name="Zoom Position",
        icon="mdi:magnify-plus-outline",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="feature_flags.can_optical_zoom",
        ufp_value="isp_settings.zoom_position",
        ufp_set_function="set_camera_zoom",
    ),
    ProtectNumberEntityDescription(
        key=_KEY_CHIME,
        name="Chime Duration",
        icon="mdi:camera-timer",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=10000,
        ufp_step=100,
        ufp_required_field="feature_flags.has_chime",
        ufp_value="chime_duration",
        ufp_set_function="set_chime_duration",
    ),
)

LIGHT_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key=_KEY_SENSITIVITY,
        name="Motion Sensitivity",
        icon="mdi:walk",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field=None,
        ufp_value="light_device_settings.pir_sensitivity",
        ufp_set_function="set_sensitivity",
    ),
    ProtectNumberEntityDescription(
        key=_KEY_DURATION,
        name="Auto-shutoff Duration",
        icon="mdi:camera-timer",
        entity_category=EntityCategory.CONFIG,
        ufp_min=15,
        ufp_max=900,
        ufp_step=15,
        ufp_required_field=None,
        ufp_value="light_device_settings.pir_duration",
        ufp_set_function="set_duration",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectNumbers,
        camera_descs=CAMERA_NUMBERS,
        light_descs=LIGHT_NUMBERS,
    )

    async_add_entities(entities)


class ProtectNumbers(ProtectDeviceEntity, NumberEntity):
    """A UniFi Protect Number Entity."""

    def __init__(
        self,
        data: ProtectData,
        device: Camera | Light,
        description: ProtectNumberEntityDescription,
    ) -> None:
        """Initialize the Number Entities."""
        self.device: Camera | Light = device
        self.entity_description: ProtectNumberEntityDescription = description
        super().__init__(data)
        self._attr_max_value = self.entity_description.ufp_max
        self._attr_min_value = self.entity_description.ufp_min
        self._attr_step = self.entity_description.ufp_step

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()

        assert self.entity_description.ufp_value is not None

        value: float | timedelta = get_nested_attr(
            self.device, self.entity_description.ufp_value
        )

        if isinstance(value, timedelta):
            self._attr_value = int(value.total_seconds())
        else:
            self._attr_value = value

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        function = self.entity_description.ufp_set_function
        _LOGGER.debug(
            "Calling %s to set %s for %s",
            function,
            value,
            self.device.name,
        )

        set_value: float | timedelta = value
        if self.entity_description.key == _KEY_DURATION:
            set_value = timedelta(seconds=value)

        await getattr(self.device, function)(set_value)
