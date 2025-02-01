"""Config flow for Home Connect."""

import logging

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Home Connect OAuth2 authentication."""

    DOMAIN = DOMAIN

    MINOR_VERSION = 3

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for Electric Kiwi."""
        await self.async_set_unique_id(DOMAIN)
        return await super().async_oauth_create_entry(data)
