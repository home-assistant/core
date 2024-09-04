"""Config flow for Weheat."""

import logging

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN, ENTRY_TITLE


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Weheat OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Override the create entry method to change to the step to find the heat pumps."""
        # setting this unique id will prevent the user from adding another weheat cloud account
        await self.async_set_unique_id(ENTRY_TITLE)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=ENTRY_TITLE, data=data)
