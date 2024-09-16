"""Config flow for Weheat."""

import logging

from weheat.abstractions.user import get_user_id_from_token

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import API_URL, DOMAIN, ENTRY_TITLE, OAUTH2_SCOPES


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Weheat OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
        }

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Override the create entry method to change to the step to find the heat pumps."""
        # get the user id and use that as unique id for this entry
        user_id = await get_user_id_from_token(
            API_URL, data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=ENTRY_TITLE, data=data)
