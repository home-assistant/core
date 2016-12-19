"""
Support for Insteon Hub lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""

from homeassistant.components.insteon_hub import INSTEON, CONF_POLL
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)

DEPENDENCIES = ['insteon_hub']

SUPPORT_INSTEON_HUB = SUPPORT_BRIGHTNESS
SUPPORTED_LIGHT_DEVICES = [
    "Switched Lighting Control",
    "Dimmable Lighting Control"
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon Hub light platform."""
    devs = []
    for device in INSTEON.devices:
        if device.DeviceCategory not in SUPPORTED_LIGHT_DEVICES:
            continue
        new_device = InsteonToggleDevice(device, discovery_info[CONF_POLL])
        INSTEON.houses[0].add_stream_callback(
            device,
            new_device.insteon_update)
        devs.append(new_device)
    add_devices(devs)


class InsteonToggleDevice(Light):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, should_poll=False):
        """Initialize the device."""
        self._should_poll = should_poll
        self.node = node
        self._value = 0

    @property
    def name(self):
        """Return the the name of the node."""
        return self.node.DeviceName

    @property
    def unique_id(self):
        """Return the ID of this insteon node."""
        return self.node.DeviceID

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value / 100 * 255

    def insteon_update(self, _):
        """Callback for an update from the hosue streaming endpoint."""
        self.schedule_update_ha_state()

    def update(self):
        """Update state of the sensor."""
        resp = self.node.send_command('get_status', wait=True)
        try:
            self._value = resp['response']['level']
            new_status = 'on' if self._value != 0 else 'off'
            self.node.set_status(new_status)
        except KeyError:
            pass

    @property
    def should_poll(self):
        """Return if polling is needed."""
        return self._should_poll

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self.node.status in ['on', 'fastOn']

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_HUB

    def turn_on(self, **kwargs):
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._value = kwargs[ATTR_BRIGHTNESS] / 255 * 100
            self.node.send_command('on', self._value)
        else:
            self._value = 100
            self.node.send_command('on')
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.send_command('off')
        self._value = 0
        self.schedule_update_ha_state()
