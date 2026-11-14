"""Config flow for the Daikin platform."""

import logging
from typing import cast, override

from daikin_onecta import (
    OnectaAccessTokenError,
    OnectaAuthenticationError,
    OnectaClient,
    OnectaRequestError,
    get_account_id,
)

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

OAUTH_SCOPES = [
    "openid",
    "onecta:basic.integration",
    "offline_access",
]


class FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    # See https://developers.home-assistant.io/docs/core/platform/application_credentials/
    VERSION = 1
    DOMAIN = DOMAIN

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an OAuth config entry."""
        try:
            unique_id = get_account_id(data["token"]["access_token"])
        except OnectaAccessTokenError:
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(unique_id)

        self._abort_if_unique_id_configured()

        access_token = cast("str", data["token"]["access_token"])

        async def async_get_access_token() -> str:
            return access_token

        client = OnectaClient(
            async_get_clientsession(self.hass), async_get_access_token
        )
        try:
            await client.get_gateway_devices()
        except OnectaAuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except OnectaRequestError:
            return self.async_abort(reason="cannot_connect")

        return await super().async_oauth_create_entry(data)

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
