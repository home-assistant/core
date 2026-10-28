"""Support for System Bridge numbers."""

from typing import override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_PORT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry
from .entity import SystemBridgeDisplayEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge numbers based on a config entry."""
    coordinator = entry.runtime_data

    # Only displays that report a brightness can have it set
    async_add_entities(
        SystemBridgeDisplayBrightnessNumber(
            coordinator, entry.data[CONF_PORT], "brightness", display.id
        )
        for display in coordinator.data.displays
        if display.brightness is not None
    )


class SystemBridgeDisplayBrightnessNumber(SystemBridgeDisplayEntity, NumberEntity):
    """Define a System Bridge display brightness number."""

    _attr_translation_key = "display_brightness"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    @override
    def native_value(self) -> float | None:
        """Return the display's brightness."""
        if (display := self._display) is None:
            return None
        return display.brightness

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the display's brightness."""
        await self._async_display_control(brightness=value)
