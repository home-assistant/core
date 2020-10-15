"""Support for SimpliSafe freeze sensor."""
from simplipy.entity import EntityTypes

from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT
from homeassistant.core import callback

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe freeze sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            SimplisafeFreezeSensor(simplisafe, system, sensor)
            for system in simplisafe.systems.values()
            for sensor in system.sensors.values()
            if sensor.type == EntityTypes.temperature
        ]
    )


class SimplisafeFreezeSensor(SimpliSafeEntity):
    """Define a SimpliSafe freeze sensor entity."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)
        self._system = system
        self._sensor = sensor
        self._state = None

    @property
    def device_class(self):
        """Return type of sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unique_id(self):
        """Return unique ID of sensor."""
        return self._sensor.serial

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        info = super().device_info
        info["identifiers"] = {(DOMAIN, self._sensor.serial)}
        info["model"] = "Freeze Sensor"
        info["name"] = self._sensor.name
        return info

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._state = self._sensor.temperature
