"""
Support for Melissa climate Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.melissa/
"""
import logging

from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['melissa']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the melissa sensor platform."""
    sensors = []
    api = hass.data[DATA_MELISSA]
    devices = api.fetch_devices().values()

    for device in devices:
        if device['type'] == 'melissa':
            sensors.append(MelissaTemperatureSensor(device, api))
            sensors.append(MelissaHumiditySensor(device, api))
    add_devices(sensors)


class MelissaSensor(Entity):
    """Representation of a Melissa Sensor."""

    _type = 'generic'

    def __init__(self, device, api):
        """Initialize the sensor."""
        self._api = api
        self._state = None
        self._name = '{0} {1}'.format(
            device['name'],
            self._type
        )
        self._serial = device['serial_number']
        self._data = device['controller_log']

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch status from melissa."""
        self._data = self._api.status(cached=True)


class MelissaTemperatureSensor(MelissaSensor):
    """Representation of a Melissa temperature Sensor."""

    _type = 'temperature'
    _unit = TEMP_CELSIUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Fetch new state data for the sensor."""
        super().update()
        try:
            self._state = self._data[self._serial]['temp']
        except KeyError:
            _LOGGER.warning("Unable to get temperature for %s", self.entity_id)


class MelissaHumiditySensor(MelissaSensor):
    """Representation of a Melissa humidity Sensor."""

    _type = 'humidity'
    _unit = '%'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Fetch new state data for the sensor."""
        super().update()
        try:
            self._state = self._data[self._serial]['humidity']
        except KeyError:
            _LOGGER.warning("Unable to get humidity for %s", self.entity_id)
