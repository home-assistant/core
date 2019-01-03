"""
Support for Tuya cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tuya/
"""
from homeassistant.components.cover import (
    CoverDevice, ENTITY_ID_FORMAT, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP)
from homeassistant.components.tuya import DATA_TUYA, TuyaDevice

DEPENDENCIES = ['tuya']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tuya cover devices."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get('dev_ids')
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaCover(device))
    add_entities(devices)


class TuyaCover(TuyaDevice, CoverDevice):
    """Tuya cover devices."""

    def __init__(self, tuya):
        """Init tuya cover device."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())

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
        state = self.tuya.state()
        if state == 1:
            return False
        if state == 2:
            return True
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
