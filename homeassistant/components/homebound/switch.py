"""
Support for HomeBoundSwitch file switch.

"""
import os
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_FILE_PATH, CONF_NAME, CONF_ID)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HomeBound switch platform."""
    file_path = config.get(CONF_FILE_PATH)
    name = config.get(CONF_NAME)
    id = config.get(CONF_ID)
    add_devices([HomeBoundSwitch(id, file_path, name)])

class HomeBoundSwitch(SwitchDevice):
    """Representation of an HomeBound switch device."""

    def __init__(self, id, file_path, name):
        """Initialize the HomeBound switch device."""
        self._on_state = False
        self._id = id
        self._name = name
        self._file_path = file_path

    @property
    def is_on(self):
        """Return whether the switch is on or off."""
        return self._on_state

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._id

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        file = open(self._file_path, 'w')
        self._on_state = True


    def turn_off(self, **kwargs):
        """Turn off the switch."""
        os.remove(self._file_path)
        self._on_state = False

