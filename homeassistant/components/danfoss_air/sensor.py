"""
Support for the for Danfoss Air HRV sensor platform.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.danfoss_air/
"""
from homeassistant.components.danfoss_air import DOMAIN \
     as DANFOSS_AIR_DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Danfoss Air sensors etc."""
    from pydanfossair.commands import ReadCommand

    data = hass.data[DANFOSS_AIR_DOMAIN]

    sensors = [
        ["Danfoss Air Exhaust Temperature", TEMP_CELSIUS,
         ReadCommand.exhaustTemperature],
        ["Danfoss Air Outdoor Temperature", TEMP_CELSIUS,
         ReadCommand.outdoorTemperature],
        ["Danfoss Air Supply Temperature", TEMP_CELSIUS,
         ReadCommand.supplyTemperature],
        ["Danfoss Air Extract Temperature", TEMP_CELSIUS,
         ReadCommand.extractTemperature],
        ["Danfoss Air Remaining Filter", '%',
         ReadCommand.filterPercent],
        ["Danfoss Air Humidity", '%',
         ReadCommand.humidity]
        ]

    dev = []

    for sensor in sensors:
        dev.append(DanfossAir(data, sensor[0], sensor[1], sensor[2]))

    add_entities(dev, True)


class DanfossAir(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, name, sensor_unit, sensor_type):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._state = None
        self._type = sensor_type
        self._unit = sensor_unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
