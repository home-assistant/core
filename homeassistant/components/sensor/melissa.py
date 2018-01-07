"""
Support for Melissa climate Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.melissa/
"""
import logging

from homeassistant.components.melissa import DOMAIN, DATA_MELISSA
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)

DEVICES_PER_SERIAL = 2


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the melissa sensor platform."""
    sensors = []
    connection = hass.data[DATA_MELISSA]
    devices = connection.fetch_devices()
    local_connection = MelissaConnection(
        connection,
        DEVICES_PER_SERIAL * len(devices)
    )
    for device in devices.values():
        sensors += [
            MelissaTemperatureSensor(
                device,
                local_connection
            ),
            MelissaHumiditySensor(
                device,
                local_connection
            )
        ]
    add_devices(sensors)


class MelissaConnection(object):
    def __init__(self, connection, num_devices):
        self._num_devices = num_devices
        self._latest_data = None
        self._connection = connection
        self.update_count = 0

    def status(self):
        if self.update_count == self._num_devices or not self._latest_data:
            self._latest_data = self._connection.status()
            self.update_count = 0
        self.update_count += 1
        return self._latest_data


class MelissaSensor(Entity):
    """Representation of a Melissa Sensor."""

    _type = 'generic'

    def __init__(self, device, connection):
        """Initialize the sensor."""
        self._connection = connection
        self._state = self.get_init_state(device['controller_log'])
        self._name = 'Melissa {0} {1}'.format(
            device['serial_number'],
            self._type
        )
        self._serial = device['serial_number']
        self._data = device['controller_log']

    def get_init_state(self, data):
        return None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        self._data = self._connection.status()


class MelissaTemperatureSensor(MelissaSensor):
    """Representation of a Melissa temperature Sensor."""

    _type = 'temperature'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def get_init_state(self, data):
        return data['temp']

    def update(self):
        """Fetch new state data for the sensor."""
        super(MelissaTemperatureSensor, self).update()
        self._state = self._data[self._serial]['temp']


class MelissaHumiditySensor(MelissaSensor):
    """Representation of a Melissa humidity Sensor."""

    _type = 'humidity'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    def get_init_state(self, data):
        return data['humidity']

    def update(self):
        """Fetch new state data for the sensor."""
        super(MelissaHumiditySensor, self).update()
        self._state = self._data[self._serial]['humidity']
