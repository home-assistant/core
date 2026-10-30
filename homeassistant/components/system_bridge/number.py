"""Support for System Bridge numbers."""

from typing import override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_PORT, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
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
    known_displays: set[str] = set()

    @callback
    def _async_add_new_displays() -> None:
        """Add brightness numbers for displays not seen before."""
        # Only displays that report a brightness can have it set
        new_displays = [
            display.id
            for display in coordinator.data.displays
            if display.brightness is not None and display.id not in known_displays
        ]
        if not new_displays:
            return
        known_displays.update(new_displays)
        async_add_entities(
            SystemBridgeDisplayBrightnessNumber(
                coordinator, entry.data[CONF_PORT], "brightness", display_id
            )
            for display_id in new_displays
        )

    _async_add_new_displays()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_displays))


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
