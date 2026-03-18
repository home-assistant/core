"""The Eight Sleep integration config flow."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class EightSleepConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eight Sleep."""

    VERSION = 1
