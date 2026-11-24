"""The Fitbit integration config flow."""

from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class FitbitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fitbit."""
