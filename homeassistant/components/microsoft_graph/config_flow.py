"""Config flow for Microsoft Graph."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_SCOPES, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Microsoft Graph OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(DEFAULT_SCOPES),
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)
