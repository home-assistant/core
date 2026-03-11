"""Config flow to configure Life360 integration."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class Life360ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Life360 integration config flow."""

    VERSION = 1
