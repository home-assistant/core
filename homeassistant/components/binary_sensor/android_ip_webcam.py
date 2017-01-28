"""
Support for IP Webcam binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.android_ip_webcam/
"""
from itertools import chain
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.components.android_ip_webcam import DATA_IP_WEBCAM

DEPENDENCIES = ['android_ip_webcam']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup IP Webcam binary sensors."""
    if discovery_info is None:
        return

    ip_webcam = hass.data[DATA_IP_WEBCAM]

    sensors = []
    for host, device in ip_webcam.items():
        conditions = discovery_info.get(CONF_MONITORED_CONDITIONS,
                                        device.enabled_sensors)
        for sensor in conditions:
            sensors.append(IPWebcamBinarySensor(device, sensor))

    add_devices(sensors, True)


class IPWebcamBinarySensor(BinarySensorDevice):
    """Represents an IP Webcam binary sensor."""

    def __init__(self, device, variable):
        """Initialize the sensor."""
        self._device = device
        self.variable = variable
        self._name = '{} {}'.format(self._device.name,
                                    self.variable.replace('_', ' '))
        self._state = None

    @property
    def name(self):
        """Return the name of the binary sensor, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state

    def update(self):
        """Retrieve latest state."""
        self._state = bool(getattr(self.device._status_data, self.variable))
