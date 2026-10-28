"""Support for System Bridge switches."""

from typing import Any, override

from systembridgeconnector.models.modules.displays import DisplayPowerState

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_PORT
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
    """Set up System Bridge switches based on a config entry."""
    coordinator = entry.runtime_data

    # Only displays that report a power state can be turned on or off
    async_add_entities(
        SystemBridgeDisplayPowerSwitch(
            coordinator, entry.data[CONF_PORT], "power", display.id
        )
        for display in coordinator.data.displays
        if display.power_state is not None
    )


class SystemBridgeDisplayPowerSwitch(SystemBridgeDisplayEntity, SwitchEntity):
    """Define a System Bridge display power switch."""

    _attr_translation_key = "display_power"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the display is on, rather than in standby, suspended or off."""
        if (display := self._display) is None or display.power_state is None:
            return None
        return display.power_state == DisplayPowerState.ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the display on."""
        await self._async_display_control(power_state=DisplayPowerState.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the display off."""
        await self._async_display_control(power_state=DisplayPowerState.OFF)
