"""ATAG water heater component."""
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, AtagEntity

OPERATION_LIST = [STATE_OFF, STATE_ECO, STATE_PERFORMANCE]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize DHW device from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AtagWaterHeater(coordinator, Platform.WATER_HEATER)])


class AtagWaterHeater(AtagEntity, WaterHeaterEntity):
    """Representation of an ATAG water heater."""

    _attr_operation_list = OPERATION_LIST
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data.dhw.temperature

    @property
    def current_operation(self):
        """Return current operation."""
        operation = self.coordinator.data.dhw.current_operation
        return operation if operation in self.operation_list else STATE_OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if await self.coordinator.data.dhw.set_temp(kwargs.get(ATTR_TEMPERATURE)):
            self.async_write_ha_state()

    @property
    def target_temperature(self):
        """Return the setpoint if water demand, otherwise return base temp (comfort level)."""
        return self.coordinator.data.dhw.target_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.coordinator.data.dhw.max_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.coordinator.data.dhw.min_temp
