"""
test.mock.switch_platform
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides a mock switch platform.

Call init before using it in your tests to ensure clean test data.
"""
import homeassistant.components as components


class MockToggleDevice(components.ToggleDevice):
    """ Fake switch. """
    def __init__(self, name, state):
        self.name = name
        self.state = state
        self.calls = []

    def get_name(self):
        """ Returns the name of the device if any. """
        self.calls.append(('get_name', {}))
        return self.name

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self.calls.append(('turn_on', kwargs))
        self.state = components.STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.calls.append(('turn_off', kwargs))
        self.state = components.STATE_OFF

    def is_on(self):
        """ True if device is on. """
        self.calls.append(('is_on', {}))
        return self.state == components.STATE_ON

    def last_call(self, method=None):
        if method is None:
            return self.calls[-1]
        else:
            return next(call for call in reversed(self.calls)
                        if call[0] == method)

DEVICES = []


def init(empty=False):
    """ (re-)initalizes the platform with devices. """
    global DEVICES

    DEVICES = [] if empty else [
        MockToggleDevice('AC', components.STATE_ON),
        MockToggleDevice('AC', components.STATE_OFF),
        MockToggleDevice(None, components.STATE_OFF)
    ]


def get_switches(hass, config):
    """ Returns mock devices. """
    return DEVICES

get_lights = get_switches
