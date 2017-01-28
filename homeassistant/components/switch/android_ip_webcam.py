"""
Support for IP Webcam settings.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.android_ip_webcam/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.android_ip_webcam import (KEY_MAP, ICON_MAP,
                                                        DATA_IP_WEBCAM)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['android_ip_webcam']
DOMAIN = 'switch'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IP Webcam switch platform."""
    if discovery_info is None:
        return

    ip_webcam = hass.data[DATA_IP_WEBCAM]

    all_switches = []

    for device in ip_webcam.values():
        for setting in discovery_info:
            all_switches.append(IPWebcamSettingsSwitch(device, setting))

    add_devices(all_switches, True)

    return True


class IPWebcamSettingsSwitch(SwitchDevice):
    """An abstract class for an IP Webcam setting."""

    def __init__(self, device, setting):
        """Initialize the settings switch."""
        self._device = device
        self._setting = setting
        self._mapped_name = KEY_MAP.get(self._setting, self._setting)
        self._name = '{} {}'.format(self._device.name, self._mapped_name)
        self._state = False

    @property
    def name(self):
        """Return the the name of the node."""
        return self._name

    def update(self):
        """Get the updated status of the switch."""
        self._device.update()
        self._state = self._device.current_settings.get(self._setting)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn device on."""
        if self._setting is 'torch':
            self._device.torch(activate=True)
        elif self._setting is 'focus':
            self._device.focus(activate=True)
        else:
            self._device.change_setting(self._setting, True)
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        if self._setting is 'torch':
            self._device.torch(activate=False)
        elif self._setting is 'focus':
            self._device.focus(activate=False)
        else:
            self._device.change_setting(self._setting, False)
        self._state = False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device.device_state_attributes

    @property
    def icon(self):
        """Return the icon for the switch."""
        return ICON_MAP.get(self._setting, 'mdi:flash')
