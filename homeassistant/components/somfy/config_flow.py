"""Config flow for Somfy."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class SomfyFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Config flow to handle Somfy OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)
