"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CONNECTIONS,
    CONF_MAX_AVAILABLE_POWER_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    CONF_NAME,
    CONF_SENSOR_TYPES,
    DOMAIN,
)


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox sensor entities in HASS."""
    coordinator = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    async_add_entities([WallboxNumber(coordinator, config)])


class WallboxNumber(CoordinatorEntity, NumberEntity):
    """Representation of the Wallbox portal."""

    def __init__(self, coordinator, config):
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        _properties = CONF_SENSOR_TYPES[CONF_MAX_CHARGING_CURRENT_KEY]
        self._coordinator = coordinator
        self._attr_name = f"{config.title} {_properties[CONF_NAME]}"
        self._device_class = _properties[CONF_DEVICE_CLASS]

    @property
    def min_value(self):
        """Return the minimum available current."""
        return 0

    @property
    def max_value(self):
        """Return the maximum available current."""
        return self._coordinator.data[CONF_MAX_AVAILABLE_POWER_KEY]

    @property
    def value(self):
        """Return the state of the sensor."""
        return self._coordinator.data[CONF_MAX_CHARGING_CURRENT_KEY]

    @property
    def device_class(self):
        """Return the state of the sensor."""
        return self._device_class

    async def async_set_value(self, value: float):
        """Set the value of the entity."""
        await self._coordinator.async_set_charging_current(value)
