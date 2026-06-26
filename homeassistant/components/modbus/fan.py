"""Support for Modbus fans."""

from typing import Any, override

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_FANS
from .entity import ModbusToggleEntity
from .modbus import ModbusHub, get_hub
from .validators import BASE_SWITCH_SCHEMA

FAN_SCHEMA = BASE_SWITCH_SCHEMA.extend({})

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modbus fans from a config entry."""
    hub = get_hub(hass, config_entry.data[CONF_NAME])
    async_add_entities(
        ModbusFan(hass, hub, config) for config in config_entry.data.get(CONF_FANS, [])
    )


class ModbusFan(ModbusToggleEntity, FanEntity):
    """Class representing a Modbus fan."""

    def __init__(
        self, hass: HomeAssistant, hub: ModbusHub, config: dict[str, Any]
    ) -> None:
        """Initialize the fan."""
        super().__init__(hass, hub, config)
        if self.command_on is not None and self._command_off is not None:
            self._attr_supported_features |= (
                FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
            )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Set fan on."""
        await self.async_turn(self.command_on)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if fan is on.

        This is needed due to the ongoing conversion of fan.
        """
        return self._attr_is_on
