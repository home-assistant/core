"""
ha_test.helper
~~~~~~~~~~~~~

Helper method for writing tests.
"""
import os

import homeassistant as ha
from homeassistant.helpers import ToggleDevice
from homeassistant.const import STATE_ON, STATE_OFF


def get_test_home_assistant():
    """ Returns a Home Assistant object pointing at test config dir. """
    hass = ha.HomeAssistant()
    hass.config_dir = os.path.join(os.path.dirname(__file__), "config")

    return hass


def mock_service(hass, domain, service):
    """
    Sets up a fake service.
    Returns a list that logs all calls to fake service.
    """
    calls = []

    hass.services.register(
        domain, service, lambda call: calls.append(call))

    return calls


class MockModule(object):
    """ Provides a fake module. """

    def __init__(self, domain, dependencies=[], setup=None):
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies
        # Setup a mock setup if none given.
        self.setup = lambda hass, config: False if setup is None else setup


class MockToggleDevice(ToggleDevice):
    """ Provides a mock toggle device. """
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
        self.state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.calls.append(('turn_off', kwargs))
        self.state = STATE_OFF

    def is_on(self):
        """ True if device is on. """
        self.calls.append(('is_on', {}))
        return self.state == STATE_ON

    def last_call(self, method=None):
        if method is None:
            return self.calls[-1]
        else:
            return next(call for call in reversed(self.calls)
                        if call[0] == method)
