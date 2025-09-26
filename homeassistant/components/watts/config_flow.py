"""Config flow for Watts Vision integration."""

import logging
from typing import Any

from visionpluspython.auth import WattsVisionAuth

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Watts Vision OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra parameters for OAuth2 authentication."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the OAuth2 flow."""

        access_token = data["token"]["access_token"]
        user_id = WattsVisionAuth.extract_user_id_from_token(access_token)

        if not user_id:
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(f"watts_vision_{user_id}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Watts Vision +",
            data=data,
        )
