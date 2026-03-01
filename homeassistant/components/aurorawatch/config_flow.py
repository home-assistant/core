"""Config flow for AuroraWatch UK integration."""

import logging

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AurowatchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AuroraWatch UK."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            # Show the form to confirm setup
            return self.async_show_form(step_id="user")

        # Create the config entry
        return self.async_create_entry(
            title="AuroraWatch UK",
            data={},
        )
