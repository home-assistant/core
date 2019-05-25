"""Support for Fritzbox binary sensors."""
import logging

import requests

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as FRITZBOX_DOMAIN

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

    add_entities(devices, True)


class FritzboxBinarySensor(BinarySensorDevice):
    """Representation of a binary Fritzbox device."""

    def __init__(self, device, fritz):
        """Initialize the Fritzbox binary sensor."""
        self._device = device
        self._fritz = fritz

    @property
    def name(self):
        """Return the name of the entity."""
        return self._device.name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'window'

    @property
    def is_on(self):
        """Return true if sensor is on."""
        if not self._device.present:
            return False
        return self._device.alert_state

    def update(self):
        """Get latest data from the Fritzbox."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            _LOGGER.warning("Connection error: %s", ex)
            self._fritz.login()
