"""Support for Ambient Weather Station binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_NAME

from . import (
    SENSOR_TYPES,
    TYPE_BATT1,
    TYPE_BATT2,
    TYPE_BATT3,
    TYPE_BATT4,
    TYPE_BATT5,
    TYPE_BATT6,
    TYPE_BATT7,
    TYPE_BATT8,
    TYPE_BATT9,
    TYPE_BATT10,
    TYPE_BATTOUT,
    AmbientWeatherEntity,
)
from .const import (
    ATTR_LAST_DATA,
    ATTR_MONITORED_CONDITIONS,
    DATA_CLIENT,
    DOMAIN,
    TYPE_BINARY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in station[ATTR_MONITORED_CONDITIONS]:
            name, _, kind, device_class = SENSOR_TYPES[condition]
            if kind == TYPE_BINARY_SENSOR:
                binary_sensor_list.append(
                    AmbientWeatherBinarySensor(
                        ambient,
                        mac_address,
                        station[ATTR_NAME],
                        condition,
                        name,
                        device_class,
                    )
                )

    async_add_entities(binary_sensor_list, True)


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorDevice):
    """Define an Ambient binary sensor."""

    @property
    def is_on(self):
        """Return the status of the sensor."""
        if self._sensor_type in (
            TYPE_BATT1,
            TYPE_BATT10,
            TYPE_BATT2,
            TYPE_BATT3,
            TYPE_BATT4,
            TYPE_BATT5,
            TYPE_BATT6,
            TYPE_BATT7,
            TYPE_BATT8,
            TYPE_BATT9,
            TYPE_BATTOUT,
        ):
            return self._state == 0

        return self._state == 1

    async def async_update(self):
        """Fetch new state data for the entity."""
        self._state = self._ambient.stations[self._mac_address][ATTR_LAST_DATA].get(
            self._sensor_type
        )
