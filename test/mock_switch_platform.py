"""
test.mock.switch_platform
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides a mock switch platform.
"""
import homeassistant.components as components


class MockSwitch(components.ToggleDevice):
    """ Fake switch. """
    def __init__(self, name, state):
        self.name = name
        self.state = state

    def get_name(self):
        """ Returns the name of the device if any. """
        return self.name

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self.state = components.STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.state = components.STATE_OFF

    def is_on(self):
        """ True if device is on. """
        return self.state == components.STATE_ON

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return {}


FAKE_NO_SWITCHES = False

SWITCHES = [
    MockSwitch('AC', components.STATE_ON),
    MockSwitch('AC', components.STATE_OFF)
]


def fake_no_switches(do_fake):
    """ Set the platform to act as if it has no switches. """
    global FAKE_NO_SWITCHES

    FAKE_NO_SWITCHES = do_fake


def get_switches(hass, config):
    """ Returns mock switches. """
    return [] if FAKE_NO_SWITCHES else SWITCHES
