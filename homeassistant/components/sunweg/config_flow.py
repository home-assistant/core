"""Config flow for Sun WEG integration."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class SunWEGConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1
