"""Config flow for the Yoto integration."""

import logging
from typing import Any

from yoto_api import YotoError, get_account_id

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import _LOGGER, DOMAIN


class YotoOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Authorize Home Assistant with a Yoto account using OAuth2."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return the logger used for the OAuth2 flow."""
        return _LOGGER

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Surface a Yoto player discovered on the local network."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Identify the Yoto account from the access token."""
        try:
            user_id = get_account_id(data["token"]["access_token"])
        except YotoError:
            return self.async_abort(reason="oauth_unauthorized")

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Yoto", data=data)
