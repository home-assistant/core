"""
homeassistant.components.switch.mock
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mock platform that has switches that have no effect

# Config takes in name of switch and initial state.
switch:
  platform: mock
  switches:
    Do the laundry: on
    Alarm active: off

"""
from homeassistant.components.switch import SwitchDevice

CONF_SWITCHES = 'switches'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    add_devices_callback(MockSwitch(name, state) for name, state
                         in config.get(CONF_SWITCHES, {}).items())


class MockSwitch(SwitchDevice):
    """ Provides a mock switch. """
    def __init__(self, name, state):
        self._name = name
        self._state = state

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

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
