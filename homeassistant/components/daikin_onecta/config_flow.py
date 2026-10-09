"""Config flow for the Daikin platform."""

from collections.abc import Mapping
import logging
from typing import Any, override

from daikin_onecta import OnectaAccessTokenError, get_account_id

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
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

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
