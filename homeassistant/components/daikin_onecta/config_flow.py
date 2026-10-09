"""Config flow for the Daikin platform."""

import logging
from typing import override

from daikin_onecta import OnectaAccessTokenError, get_account_id

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

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
    MINOR_VERSION = 2
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
        return await super().async_oauth_create_entry(data)

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
