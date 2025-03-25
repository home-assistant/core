"""Config flow for Ondilo ICO."""

import logging
from typing import Any

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET


class OndiloIcoOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Ondilo ICO OAuth2 authentication."""

    DOMAIN = DOMAIN

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        # Import the default client credential.
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Ondilo ICO"),
        )
        return await super().async_step_user(user_input)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "api"}
