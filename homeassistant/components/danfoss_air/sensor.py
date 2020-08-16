"""Support for the for Danfoss Air HRV sensors."""
import logging

from pydanfossair.commands import ReadCommand

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from . import DOMAIN as DANFOSS_AIR_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Danfoss Air sensors etc."""
    data = hass.data[DANFOSS_AIR_DOMAIN]

    sensors = [
        [
            "Danfoss Air Exhaust Temperature",
            TEMP_CELSIUS,
            ReadCommand.exhaustTemperature,
            DEVICE_CLASS_TEMPERATURE,
        ],
        [
            "Danfoss Air Outdoor Temperature",
            TEMP_CELSIUS,
            ReadCommand.outdoorTemperature,
            DEVICE_CLASS_TEMPERATURE,
        ],
        [
            "Danfoss Air Supply Temperature",
            TEMP_CELSIUS,
            ReadCommand.supplyTemperature,
            DEVICE_CLASS_TEMPERATURE,
        ],
        [
            "Danfoss Air Extract Temperature",
            TEMP_CELSIUS,
            ReadCommand.extractTemperature,
            DEVICE_CLASS_TEMPERATURE,
        ],
        [
            "Danfoss Air Remaining Filter",
            UNIT_PERCENTAGE,
            ReadCommand.filterPercent,
            None,
        ],
        [
            "Danfoss Air Humidity",
            UNIT_PERCENTAGE,
            ReadCommand.humidity,
            DEVICE_CLASS_HUMIDITY,
        ],
        ["Danfoss Air Fan Step", UNIT_PERCENTAGE, ReadCommand.fan_step, None],
        ["Danfoss Air Exhaust Fan Speed", "RPM", ReadCommand.exhaust_fan_speed, None],
        ["Danfoss Air Supply Fan Speed", "RPM", ReadCommand.supply_fan_speed, None],
        [
            "Danfoss Air Dial Battery",
            UNIT_PERCENTAGE,
            ReadCommand.battery_percent,
            DEVICE_CLASS_BATTERY,
        ],
    ]

    dev = []

    for sensor in sensors:
        dev.append(DanfossAir(data, sensor[0], sensor[1], sensor[2], sensor[3]))

    add_entities(dev, True)


class DanfossAir(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, name, sensor_unit, sensor_type, device_class):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._state = None
        self._type = sensor_type
        self._unit = sensor_unit
        self._device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Update the new state of the sensor.

        This is done through the DanfossAir object that does the actual
        communication with the Air CCM.
        """
        self._data.update()

        self._state = self._data.get_value(self._type)
        if self._state is None:
            _LOGGER.debug("Could not get data for %s", self._type)
