"""
homeassistant.components.switch.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo platform that has two fake switches.
"""
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import DEVICE_DEFAULT_NAME


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    add_devices_callback([
        DemoSwitch('Decorative Lights', True, None),
        DemoSwitch('AC', False, 'mdi:air-conditioner')
    ])


class DemoSwitch(SwitchDevice):
    """ Provides a demo switch. """
    def __init__(self, name, state, icon):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo switch. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def icon(self):
        """ Returns the icon to use for device if any. """
        return self._icon

    @property
    def current_power_mwh(self):
        """ Current power usage in mwh. """
        if self._state:
            return 100

    @property
    def today_power_mw(self):
        """ Today total power usage in mw. """
        return 1500

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self.update_ha_state()
