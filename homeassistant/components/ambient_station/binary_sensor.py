"""Support for Ambient Weather Station binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_NAME

from . import (
    SENSOR_TYPES, TYPE_BATT1, TYPE_BATT2, TYPE_BATT3, TYPE_BATT4, TYPE_BATT5,
    TYPE_BATT6, TYPE_BATT7, TYPE_BATT8, TYPE_BATT9, TYPE_BATT10, TYPE_BATTOUT,
    AmbientWeatherEntity)
from .const import ATTR_LAST_DATA, DATA_CLIENT, DOMAIN, TYPE_BINARY_SENSOR

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ambient_station']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Ambient PWS binary sensors based on the old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in ambient.monitored_conditions:
            name, _, kind, device_class = SENSOR_TYPES[condition]
            if kind == TYPE_BINARY_SENSOR:
                binary_sensor_list.append(
                    AmbientWeatherBinarySensor(
                        ambient, mac_address, station[ATTR_NAME], condition,
                        name, device_class))

    async_add_entities(binary_sensor_list, True)


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorDevice):
    """Define an Ambient binary sensor."""

    def __init__(
            self, ambient, mac_address, station_name, sensor_type, sensor_name,
            device_class):
        """Initialize the sensor."""
        super().__init__(
            ambient, mac_address, station_name, sensor_type, sensor_name)

        self._device_class = device_class

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_on(self):
        """Return the status of the sensor."""
        if self._sensor_type in (TYPE_BATT1, TYPE_BATT10, TYPE_BATT2,
                                 TYPE_BATT3, TYPE_BATT4, TYPE_BATT5,
                                 TYPE_BATT6, TYPE_BATT7, TYPE_BATT8,
                                 TYPE_BATT9, TYPE_BATTOUT):
            return self._state == 0

        return self._state == 1

    async def async_update(self):
        """Fetch new state data for the entity."""
        self._state = self._ambient.stations[
            self._mac_address][ATTR_LAST_DATA].get(self._sensor_type)
