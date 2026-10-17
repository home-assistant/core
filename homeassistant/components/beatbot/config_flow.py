"""Config flow for the Beatbot integration."""

import logging
from typing import Any, override

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotClient,
    BeatbotConnectionError,
    decode_access_token,
)
from beatbot_cloud.const import OAUTH2_CLIENT_ID, REGION_API_BASE_URL

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BeatbotConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Beatbot."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the flow logger."""
        return _LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start a flow using Beatbot's public OAuth client."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(OAUTH2_CLIENT_ID, "", name="Beatbot"),
        )
        return await super().async_step_user(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry using identity and region token claims."""
        access_token = (data.get("token") or {}).get("access_token")
        claims = (
            decode_access_token(access_token) if isinstance(access_token, str) else None
        )
        if claims is None or not isinstance(sub := claims.get("sub"), str) or not sub:
            return self.async_abort(reason="oauth_error")

        await self.async_set_unique_id(sub)
        if region := claims.get("region"):
            data["region"] = str(region)
        if data.get("region") not in REGION_API_BASE_URL:
            return self.async_abort(reason="unknown_region")

        self._abort_if_unique_id_configured()
        if abort_result := await self._async_validate_resource_api(data):
            return abort_result
        return self.async_create_entry(title="Beatbot", data=data)

    async def _async_validate_resource_api(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult | None:
        """Verify the token can access the regional device API."""
        client = BeatbotClient(
            data["region"],
            async_get_clientsession(self.hass),
            data["token"]["access_token"],
        )
        try:
            await client.get_devices()
        except BeatbotAuthenticationError:
            return self.async_abort(reason="oauth_error")
        except BeatbotConnectionError:
            return self.async_abort(reason="cannot_connect")
        return None
