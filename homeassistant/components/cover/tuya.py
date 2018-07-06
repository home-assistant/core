"""
Support for Tuya cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tuya/
"""
import asyncio

from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP)
from homeassistant.components.tuya import DOMAIN, DATA_TUYA, TuyaDevice

DEPENDENCIES = ['tuya']

DEVICE_TYPE = 'cover'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya cover devices."""
    tuya = hass.data[DATA_TUYA]
    devices = tuya.get_devices_by_type(DEVICE_TYPE)

    if DEVICE_TYPE not in hass.data[DOMAIN]['entities']:
        hass.data[DOMAIN]['entities'][DEVICE_TYPE] = []

    for device in devices:
        if device.object_id() not in hass.data[DOMAIN]['dev_ids']:
            add_devices([TuyaCover(device, hass)])
            hass.data[DOMAIN]['dev_ids'].append(device.object_id())


class TuyaCover(TuyaDevice, CoverDevice):
    """Tuya cover devices."""

    def __init__(self, tuya, hass):
        """Init tuya cover device."""
        super(TuyaCover, self).__init__(tuya, hass)
        self.entity_id = DEVICE_TYPE + '.' + tuya.object_id()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities'][DEVICE_TYPE].append(self)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
        if self.tuya.support_stop():
            supported_features |= SUPPORT_STOP
        return supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.tuya.open_cover()

    def close_cover(self, **kwargs):
        """Close cover."""
        self.tuya.close_cover()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.tuya.stop_cover()
