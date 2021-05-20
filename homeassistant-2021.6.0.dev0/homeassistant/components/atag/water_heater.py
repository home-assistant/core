"""ATAG water heater component."""
from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
)
from homeassistant.const import STATE_OFF, TEMP_CELSIUS

from . import DOMAIN, WATER_HEATER, AtagEntity

SUPPORT_FLAGS_HEATER = 0
OPERATION_LIST = [STATE_OFF, STATE_ECO, STATE_PERFORMANCE]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize DHW device from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AtagWaterHeater(coordinator, WATER_HEATER)])


class AtagWaterHeater(AtagEntity, WaterHeaterEntity):
    """Representation of an ATAG water heater."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data.dhw.temperature

    @property
    def current_operation(self):
        """Return current operation."""
        operation = self.coordinator.data.dhw.current_operation
        return operation if operation in self.operation_list else STATE_OFF

    @property
    def operation_list(self):
        """List of available operation modes."""
        return OPERATION_LIST

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if await self.coordinator.data.dhw.set_temp(kwargs.get(ATTR_TEMPERATURE)):
            self.async_write_ha_state()

    @property
    def target_temperature(self):
        """Return the setpoint if water demand, otherwise return base temp (comfort level)."""
        return self.coordinator.data.dhw.target_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.coordinator.data.dhw.max_temp

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.coordinator.data.dhw.min_temp
