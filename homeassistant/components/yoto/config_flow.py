"""Config flow for the Yoto integration."""

import logging
from typing import Any

from yoto_api import YotoError, get_account_id

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import _LOGGER, DOMAIN, YOTO_AUDIENCE, YOTO_SCOPES


class YotoOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Authorize Home Assistant with a Yoto account using OAuth2."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return the logger used for the OAuth2 flow."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Append Yoto's audience and scopes to the authorize URL."""
        return {
            "audience": YOTO_AUDIENCE,
            "scope": " ".join(YOTO_SCOPES),
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Identify the Yoto account from the access token."""
        try:
            user_id = get_account_id(data["token"]["access_token"])
        except YotoError:
            return self.async_abort(reason="oauth_unauthorized")

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Yoto", data=data)
