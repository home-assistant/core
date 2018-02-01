"""
Support for Orvibo S20 Wifi Smart Switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.orvibo/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_SWITCHES, CONF_MAC, CONF_DISCOVERY)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['orvibo==1.1.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Orvibo S20 Switch'
DEFAULT_DISCOVERY = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES, default=[]):
        vol.All(cv.ensure_list, [{
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_MAC): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
        }]),
    vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up S20 switches."""
    from orvibo.s20 import discover, S20, S20Exception

    switch_data = {}
    switches = []
    switch_conf = config.get(CONF_SWITCHES, [config])

    if config.get(CONF_DISCOVERY):
        _LOGGER.info("Discovering S20 switches ...")
        switch_data.update(discover())

    for switch in switch_conf:
        switch_data[switch.get(CONF_HOST)] = switch

    for host, data in switch_data.items():
        try:
            switches.append(S20Switch(data.get(CONF_NAME),
                                      S20(host, mac=data.get(CONF_MAC))))
            _LOGGER.info("Initialized S20 at %s", host)
        except S20Exception:
            _LOGGER.error("S20 at %s couldn't be initialized", host)

    add_devices_callback(switches)


class S20Switch(SwitchDevice):
    """Representation of an S20 switch."""

    def __init__(self, name, s20):
        """Initialize the S20 device."""
        from orvibo.s20 import S20Exception

        self._name = name
        self._s20 = s20
        self._state = False
        self._exc = S20Exception

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        try:
            self._state = self._s20.on
        except self._exc:
            _LOGGER.exception("Error while fetching S20 state")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            self._s20.on = True
        except self._exc:
            _LOGGER.exception("Error while turning on S20")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            self._s20.on = False
        except self._exc:
            _LOGGER.exception("Error while turning off S20")
