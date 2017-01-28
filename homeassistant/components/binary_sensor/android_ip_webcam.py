"""
Support for IP Webcam binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.android_ip_webcam/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.android_ip_webcam import (KEY_MAP,
                                                        DATA_IP_WEBCAM)

DEPENDENCIES = ['android_ip_webcam']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup IP Webcam binary sensors."""
    if discovery_info is None:
        return

    ip_webcam = hass.data[DATA_IP_WEBCAM]

    for device in ip_webcam.values():
        add_devices([IPWebcamBinarySensor(device, 'motion_active')], True)


class IPWebcamBinarySensor(BinarySensorDevice):
    """Represents an IP Webcam binary sensor."""

    def __init__(self, device, variable):
        """Initialize the sensor."""
        self._device = device
        self.variable = variable
        self._mapped_name = KEY_MAP.get(self.variable, self.variable)
        self._name = '{} {}'.format(self._device.name, self._mapped_name)
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the binary sensor, if any."""
        return self._name

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state

    def update(self):
        """Retrieve latest state."""
        self._device.update()
        container = self._device.sensor_data.get(self.variable)
        data_point = container.get('data', [[0, [0.0]]])
        self._state = data_point[0][-1][0] == 1.0

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return 'mdi:run' if self._state else 'mdi:walk'
