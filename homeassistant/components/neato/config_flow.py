"""Config flow for Neato Botvac."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

# pylint: disable=unused-import
from .const import NEATO_DOMAIN

DOCS_URL = "https://www.home-assistant.io/integrations/neato"

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=NEATO_DOMAIN
):
    """Config flow to handle Neato Botvac OAuth2 authentication."""

    VERSION = 2
    DOMAIN = NEATO_DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None) -> dict:
        """Create an entry for the flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await super().async_step_user(user_input=user_input)

    async def async_step_reauth(self, entry_data) -> dict:
        """Perform reauth upon migration of old entries."""
        # TODO: delete current entries
        return self.async_show_form(step_id="pick_implementation")
