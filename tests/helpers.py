"""
tests.helper
~~~~~~~~~~~~~

Helper method for writing tests.
"""
import os
from datetime import timedelta

import homeassistant as ha
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME, EVENT_TIME_CHANGED)
from homeassistant.components import sun


def get_test_config_dir():
    """ Returns a path to a test config dir. """
    return os.path.join(os.path.dirname(__file__), "config")


def get_test_home_assistant():
    """ Returns a Home Assistant object pointing at test config dir. """
    hass = ha.HomeAssistant()
    hass.config.config_dir = get_test_config_dir()
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

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


def trigger_device_tracker_scan(hass):
    """ Triggers the device tracker to scan. """
    hass.bus.fire(
        EVENT_TIME_CHANGED,
        {'now':
         dt_util.utcnow().replace(second=0) + timedelta(hours=1)})


def ensure_sun_risen(hass):
    """ Trigger sun to rise if below horizon. """
    if not sun.is_on(hass):
        hass.bus.fire(
            EVENT_TIME_CHANGED,
            {'now':
             sun.next_rising_utc(hass) + timedelta(seconds=10)})


def ensure_sun_set(hass):
    """ Trigger sun to set if above horizon. """
    if sun.is_on(hass):
        hass.bus.fire(
            EVENT_TIME_CHANGED,
            {'now':
             sun.next_setting_utc(hass) + timedelta(seconds=10)})


class MockModule(object):
    """ Provides a fake module. """

    def __init__(self, domain, dependencies=[], setup=None):
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies
        # Setup a mock setup if none given.
        self.setup = lambda hass, config: False if setup is None else setup


class MockToggleDevice(ToggleEntity):
    """ Provides a mock toggle device. """
    def __init__(self, name, state):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self.calls = []

    @property
    def name(self):
        """ Returns the name of the device if any. """
        self.calls.append(('name', {}))
        return self._name

    @property
    def state(self):
        """ Returns the name of the device if any. """
        self.calls.append(('state', {}))
        return self._state

    @property
    def is_on(self):
        """ True if device is on. """
        self.calls.append(('is_on', {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self.calls.append(('turn_on', kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.calls.append(('turn_off', kwargs))
        self._state = STATE_OFF

    def last_call(self, method=None):
        if not self.calls:
            return None
        elif method is None:
            return self.calls[-1]
        else:
            try:
                return next(call for call in reversed(self.calls)
                            if call[0] == method)
            except StopIteration:
                return None
