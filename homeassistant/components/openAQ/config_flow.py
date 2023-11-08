"""Adds config flow for OpenAQ."""

from .const import DOMAIN

from homeassistant import config_entries


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    def __init__(self):
        """Initialize."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Handle user initiated configuration."""
        pass
