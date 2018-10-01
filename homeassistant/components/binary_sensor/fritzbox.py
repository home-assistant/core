"""
Support for Fritzbox binary sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.fritzbox/
"""
import logging
import requests

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.fritzbox import DOMAIN as FRITZBOX_DOMAIN

DEPENDENCIES = ['fritzbox']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fritzbox binary sensor platform."""
    devices = []
    fritz_list = hass.data[FRITZBOX_DOMAIN]

    for fritz in fritz_list:
        device_list = fritz.get_devices()
        for device in device_list:
            if device.has_alarm:
                devices.append(FritzboxBinarySensor(device, fritz))

    add_entities(devices)


class FritzboxBinarySensor(BinarySensorDevice):
    """Representation of a binary Fritzbox device."""

    def __init__(self, device, fritz):
        """Initialize the sensor."""
        self._device = device
        self._fritz = fritz
        self._sensor_type = 'window'

    @property
    def name(self):
        """Return the name of the entity."""
        return self._device.name

    @property
    def should_poll(self):
        """Polling needed."""
        return True

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return true if sensor is on."""
        if not self._device.present:
            return False
        return self._device.alert_state

    def update(self):
        """Get latest data from the fritzbox."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            _LOGGER.warning("Fritzbox connection error: %s", ex)
            self._fritz.login()
