"""Support for Ambient Weather Station sensors."""
import logging

from homeassistant.components.ambient_station import (
    SENSOR_TYPES, AmbientWeatherEntity)
from homeassistant.const import ATTR_NAME

from .const import ATTR_LAST_DATA, DATA_CLIENT, DOMAIN, TYPE_SENSOR

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ambient_station']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Ambient PWS sensors based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in ambient.monitored_conditions:
            name, unit, kind, _ = SENSOR_TYPES[condition]
            if kind == TYPE_SENSOR:
                sensor_list.append(
                    AmbientWeatherSensor(
                        ambient, mac_address, station[ATTR_NAME], condition,
                        name, unit))

    async_add_entities(sensor_list, True)


class AmbientWeatherSensor(AmbientWeatherEntity):
    """Define an Ambient sensor."""

    def __init__(
            self, ambient, mac_address, station_name, sensor_type, sensor_name,
            unit):
        """Initialize the sensor."""
        super().__init__(
            ambient, mac_address, station_name, sensor_type, sensor_name)

        self._unit = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        self._state = self._ambient.stations[
            self._mac_address][ATTR_LAST_DATA].get(self._sensor_type)
