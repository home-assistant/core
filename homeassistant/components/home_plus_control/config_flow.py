"""Config flow for Legrand Home+ Control."""
import logging

from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class HomePlusControlFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Home+ Control OAuth2 authentication."""

    DOMAIN = DOMAIN

    # Pick the Cloud Poll class

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        """Handle a flow start initiated by the user."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)
