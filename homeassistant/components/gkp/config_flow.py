"""Config flow for GKP integration."""

import logging
from typing import Any, override

from gkphomepython import GkpAuth

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle GKP OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra parameters for OAuth2 authentication."""
        return {"scope": " ".join(OAUTH2_SCOPES)}

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the OAuth2 flow."""
        user_id = GkpAuth.extract_user_id_from_token(data["token"]["access_token"])

        if not user_id:
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(user_id)

        self._abort_if_unique_id_configured()

        return self.async_create_entry(title="GKP Home", data=data)
