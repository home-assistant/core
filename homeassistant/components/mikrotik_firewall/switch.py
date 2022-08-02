"""Mikrotik firewall rule switch."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.switch import SwitchEntity
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_HOST,
    CONF_PASS,
    CONF_RULE_ID,
    CONF_RULE_NAME,
    CONF_RULES,
    CONF_USER,
)

RULE_SCHEMA = vol.Schema(
    {vol.Required(CONF_RULE_ID): cv.string, vol.Optional(CONF_RULE_NAME): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # router ip
        vol.Required(CONF_HOST): cv.string,
        # username
        vol.Required(CONF_USER): cv.string,
        # password, can be empty
        vol.Optional(CONF_PASS): cv.string,
        # rules
        vol.Required(CONF_RULES): vol.All(cv.ensure_list, [RULE_SCHEMA]),
    }
)


class RuleSwitch(SwitchEntity):
    """Firewall rule switch."""

    def __init__(self):
        """Class setup."""
        self._is_on = False

    @property
    def name(self):
        """Name of the entity."""
        return "My Switch"

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._is_on = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._is_on = False
