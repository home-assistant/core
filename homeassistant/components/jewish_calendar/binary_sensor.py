"""Support for Jewish Calendar binary sensors."""
import logging

import hdate

from homeassistant.components.binary_sensor import BinarySensorEntity
import homeassistant.util.dt as dt_util

from . import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish Calendar binary sensor devices."""
    if discovery_info is None:
        return

    async_add_entities(
        [
            JewishCalendarBinarySensor(hass.data[DOMAIN], sensor, sensor_info)
            for sensor, sensor_info in SENSOR_TYPES["binary"].items()
        ]
    )


class JewishCalendarBinarySensor(BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    def __init__(self, data, sensor, sensor_info):
        """Initialize the binary sensor."""
        self._location = data["location"]
        self._type = sensor
        self._name = f"{data['name']} {sensor_info[0]}"
        self._icon = sensor_info[1]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._state = False
        self._prefix = data["prefix"]

    @property
    def icon(self):
        """Return the icon of the entity."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Generate a unique id."""
        return f"{self._prefix}_{self._type}"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        zmanim = hdate.Zmanim(
            date=dt_util.now(),
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

        self._state = zmanim.issur_melacha_in_effect
