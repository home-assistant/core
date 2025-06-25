"""Config flow for Spider integration."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class SpiderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Spider."""

    VERSION = 1
