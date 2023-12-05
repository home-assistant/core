"""Config flow for Shelly Button Manager integration."""

from homeassistant import config_entries

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Shelly Button Manager config flow."""

    VERSION = 1
