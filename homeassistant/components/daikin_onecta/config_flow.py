"""Config flow for the Daikin platform."""

from collections.abc import Mapping
import logging
from typing import Any, cast, override

from daikin_onecta import (
    OnectaAccessTokenError,
    OnectaAuthenticationError,
    OnectaClient,
    OnectaRequestError,
    get_account_id,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication after an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication and restart OAuth authorization."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an OAuth config entry."""
        try:
            unique_id = get_account_id(data["token"]["access_token"])
        except OnectaAccessTokenError:
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(unique_id)
        access_token = cast("str", data["token"]["access_token"])

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            if reauth_entry.unique_id is not None:
                self._abort_if_unique_id_mismatch(reason="wrong_account")
            if reason := await self._async_test_api_access(access_token):
                return self.async_abort(reason=reason)
            return self.async_update_reload_and_abort(
                reauth_entry, unique_id=unique_id, data=data
            )

        self._abort_if_unique_id_configured()

        if reason := await self._async_test_api_access(access_token):
            return self.async_abort(reason=reason)

        return await super().async_oauth_create_entry(data)

    async def _async_test_api_access(self, access_token: str) -> str | None:
        """Test the gateway API with the newly authorized token."""

        async def async_get_access_token() -> str:
            return access_token

        client = OnectaClient(
            async_get_clientsession(self.hass), async_get_access_token
        )
        try:
            await client.get_gateway_devices()
        except OnectaAuthenticationError:
            return "invalid_auth"
        except OnectaRequestError:
            return "cannot_connect"
        return None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
