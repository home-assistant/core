"""Config flow for MyPermobil integration."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class PermobilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Permobil integration config flow."""

    VERSION = 1
