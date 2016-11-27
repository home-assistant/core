"""
Support for Digital Loggers Inc Web Power Controllers

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.dli/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_URL, CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['dlipower==0.7.165']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Web Power Controller."""
    import dlipower
    switch = dlipower.PowerSwitch(hostname=config.get(CONF_URL),
                                  userid=config.get(CONF_USERNAME),
                                  password=config.get(CONF_PASSWORD))
    switches = []
    for outlet in switch.statuslist():
        if outlet[2] == 'ON':
            state = True
        else:
            state = False
        if outlet[1] is None:
            switches.append(
                DLISwitch(
                    outlet[0],
                    config.get(CONF_URL) + ':' + str(outlet[0]),
                    state,
                    switch
                )
            )
        else:
            switches.append(DLISwitch(outlet[0], outlet[1], outlet[2], switch))
    add_devices(switches)


class DLISwitch(SwitchDevice):
    """Resresentatin of a WPC Switched Outlet."""

    def __init__(self, number, name, state, switch):
        """Init the Outlet."""
        self._number = number
        self._name = name
        self._state = state
        self._switch = switch

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        if self._switch.status(self._number) == 'ON':
            self._state = True
        else:
            self._state = False
        return self._state

    def turn_on(self):
        """Turn the device on."""
        self._switch.on(self._number)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the device off."""
        self._switch.off(self._number)
        self._state = False
        self.schedule_update_ha_state()
