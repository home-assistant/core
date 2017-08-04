"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_vacuum/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (DEVICE_DEFAULT_NAME,
                                 CONF_NAME, CONF_HOST, CONF_TOKEN)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME): cv.string,
})

REQUIREMENTS = ['python-mirobo==0.1.2']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the vacuum from config."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    add_devices_callback([MiroboSwitch(name, host, token)], True)


class MiroboSwitch(SwitchDevice):
    """Representation of a Xiaomi Vacuum."""

    def __init__(self, name, host, token):
        """Initialize the vacuum switch."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._icon = 'mdi:broom'
        self.host = host
        self.token = token

        self._vacuum = None
        self._state = None
        self._state_attrs = {}
        self._is_on = False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def vacuum(self):
        """Property accessor for vacuum object."""
        if not self._vacuum:
            from mirobo import Vacuum
            _LOGGER.info("initializing with host %s token %s",
                         self.host, self.token)
            self._vacuum = Vacuum(self.host, self.token)

        return self._vacuum

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        from mirobo import VacuumException
        try:
            self.vacuum.start()
            self._is_on = True
        except VacuumException as ex:
            _LOGGER.error("Unable to start the vacuum: %s", ex)

    def turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        from mirobo import VacuumException
        try:
            self.vacuum.stop()
            self.vacuum.home()
            self._is_on = False
        except VacuumException as ex:
            _LOGGER.error("Unable to turn off and return home: %s", ex)

    def update(self):
        """Fetch state from the device."""
        from mirobo import DeviceException
        try:
            state = self.vacuum.status()
            _LOGGER.debug("got state from the vacuum: %s", state)

            self._state_attrs = {
                'Status': state.state, 'Error': state.error,
                'Battery': state.battery, 'Fan': state.fanspeed,
                'Cleaning time': str(state.clean_time),
                'Cleaned area': state.clean_area}

            self._state = state.state_code
            self._is_on = state.is_on
        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)
