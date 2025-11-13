"""Config flow for nVent RAYCHEM SENZ."""

import logging

import jwt

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle SENZ OAuth2 authentication."""

    VERSION = 1
    MINOR_VERSION = 2
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "restapi offline_access"}

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create or update the config entry."""

        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )
        uid = token["sub"]
        await self.async_set_unique_id(uid)

        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
