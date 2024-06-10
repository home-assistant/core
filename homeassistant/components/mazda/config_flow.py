"""The Mazda Connected Services integration."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class MazdaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mazda Connected Services."""

    VERSION = 1
