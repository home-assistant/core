"""Number Selectors for Lyngdorf Integration."""

from typing import cast

from lyngdorf.device import Receiver

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ICON_TRIM_BASS,
    ICON_TRIM_CENTRE,
    ICON_TRIM_HEIGHT,
    ICON_TRIM_LFE,
    ICON_TRIM_SURROUND,
    ICON_TRIM_TREBLE,
)
from .models import LyngdorfConfigEntry

TRIMS = {
    "trim_bass": {
        "min": -12.0,
        "max": 12.0,
        "icon": ICON_TRIM_BASS,
        "name": "Bass Trim",
        "step": 0.5,
    },
    "trim_treble": {
        "min": -12.0,
        "max": 12.0,
        "icon": ICON_TRIM_TREBLE,
        "name": "Treble Trim",
        "step": 0.5,
    },
    "trim_centre": {
        "min": -10.0,
        "max": 10.0,
        "icon": ICON_TRIM_CENTRE,
        "name": "Centre Trim",
        "step": 1.0,
    },
    "trim_height": {
        "min": -10.0,
        "max": 10.0,
        "icon": ICON_TRIM_HEIGHT,
        "name": "Height Trim",
        "step": 1.0,
    },
    "trim_lfe": {
        "min": -10.0,
        "max": 10.0,
        "icon": ICON_TRIM_LFE,
        "name": "LFE Trim",
        "step": 1.0,
    },
    "trim_surround": {
        "min": -10.0,
        "max": 10.0,
        "icon": ICON_TRIM_SURROUND,
        "name": "Surround Trim",
        "step": 1.0,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    receiver = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    entities = [
        TrimEntity(
            receiver,
            config_entry,
            device_info,
            prop_name,
            cast(float, info["min"]),
            cast(float, info["max"]),
            cast(str, info["icon"]),
            cast(float, info["step"]),
            cast(str, info["name"]),
        )
        for prop_name, info in TRIMS.items()
    ]

    async_add_entities(entities, update_before_add=True)


class TrimEntity(NumberEntity):
    """Trim Slider Entity."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        property: str,
        min: float,
        max: float,
        icon: str,
        step: float,
        name: str,
    ) -> None:
        """Create Trim Slider Entity."""
        self._attr_has_entity_name = True
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{property}"
        self._receiver = receiver
        self._attr_device_class = NumberDeviceClass.SOUND_PRESSURE
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = min
        self._attr_native_max_value = max
        self._attr_native_step = step
        self._property = property

    def set_native_value(self, value: float) -> None:
        """Native value in the receiver."""
        setattr(self._receiver, self._property, value)

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the receiver."""
        return cast(float, getattr(self._receiver, self._property))

    async def async_added_to_hass(self) -> None:
        """Notify of addition to haas."""
        self._receiver.register_notification_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Notify of removal from haas."""
        self._receiver.un_register_notification_callback(self.async_write_ha_state)
