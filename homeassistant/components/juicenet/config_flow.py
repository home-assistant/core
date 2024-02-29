"""Config flow for JuiceNet integration."""

from homeassistant import config_entries

from . import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JuiceNet."""

    VERSION = 1
