"""Support for the for Danfoss Air HRV binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as DANFOSS_AIR_DOMAIN


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Danfoss Air sensors etc."""
    from pydanfossair.commands import ReadCommand
    data = hass.data[DANFOSS_AIR_DOMAIN]

    sensors = [
        ["Danfoss Air Bypass Active", ReadCommand.bypass, "opening"],
        ["Danfoss Air Away Mode Active", ReadCommand.away_mode, None],
    ]

    dev = []

    for sensor in sensors:
        dev.append(DanfossAirBinarySensor(
            data, sensor[0], sensor[1], sensor[2]))

    add_entities(dev, True)


class DanfossAirBinarySensor(BinarySensorDevice):
    """Representation of a Danfoss Air binary sensor."""

    def __init__(self, data, name, sensor_type, device_class):
        """Initialize the Danfoss Air binary sensor."""
        self._data = data
        self._name = name
        self._state = None
        self._type = sensor_type
        self._device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Type of device class."""
        return self._device_class

    def update(self):
        """Fetch new state data for the sensor."""
        self._data.update()

        self._state = self._data.get_value(self._type)
