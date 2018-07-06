"""
Support for the Tuya devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.tuya/
"""

import asyncio

from homeassistant.components.scene import Scene
from homeassistant.components.tuya import (DOMAIN, DATA_TUYA, TuyaDevice)

DEPENDENCIES = ['tuya']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya scenes."""
    tuya = hass.data[DATA_TUYA]
    devices = tuya.get_devices_by_type('scene')

    if 'scene' not in hass.data[DOMAIN]['entities']:
        hass.data[DOMAIN]['entities']['scene'] = []
    for device in devices:
        if device.object_id() not in hass.data[DOMAIN]['dev_ids']:
            add_devices([TuyaScene(device, hass)])
            hass.data[DOMAIN]['dev_ids'].append(device.object_id())


class TuyaScene(TuyaDevice, Scene):
    """Tuya Scene."""

    def __init__(self, tuya, hass):
        """Init Tuya scene."""
        super(TuyaScene, self).__init__(tuya, hass)
        self.entity_id = 'scene.' + tuya.object_id().lower()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['scene'].append(self)

    def activate(self):
        """Activate the scene."""
        self.tuya.activate()

    @property
    def should_poll(self):
        """Scene has no data."""
        return False
