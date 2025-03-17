"""Config flow for Actron Air."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Actron Air OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "ac-system-access"}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Ensure unique entry by setting a unique ID based on user account."""
        await self.async_set_unique_id(data["token"]["user_id"])  # Ensure unique ID
        self._abort_if_unique_id_configured()  # Prevent duplicate entries
        return await super().async_oauth_create_entry(data)  # Correct return type
