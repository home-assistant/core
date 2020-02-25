"""Support for powering on/off server with HP iLO."""
import logging

import hpilo
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HP ILO"
DEFAULT_PORT = 443

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HP iLO switch."""
    hostname = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    login = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config[CONF_NAME]

    try:
        hp_ilo = hpilo.Ilo(hostname=hostname, login=login, password=password, port=port)
    except ValueError as error:
        _LOGGER.error(error)
        return

    add_entities([HpIloSwitch(hass, name, hp_ilo)], True)


class HpIloSwitch(SwitchDevice):
    """Representation of a HP iLO switch."""

    def __init__(self, hass, name, hp_ilo):
        """Initialize the HP iLO switch."""
        self._hass = hass
        self._name = name
        self.hp_ilo = hp_ilo
        self._state = None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.hp_ilo.set_host_power(True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.hp_ilo.set_host_power(False)

    def update(self):
        """Update the server's power state."""
        pwr_status = self.hp_ilo.get_host_power_status().lower()

        if pwr_status in (STATE_ON, STATE_OFF):
            self._state = pwr_status
        else:
            self._state = None
