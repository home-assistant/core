"""Config flow for the Yoto integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from yoto_api import YotoError, get_account_id

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import _LOGGER, DOMAIN, YOTO_AUDIENCE, YOTO_SCOPES


class YotoOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Authorize Home Assistant with a Yoto account using OAuth2."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the logger used for the OAuth2 flow."""
        return _LOGGER

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Append Yoto's audience and scopes to the authorize URL."""
        return {
            "audience": YOTO_AUDIENCE,
            "scope": " ".join(YOTO_SCOPES),
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth and restart the OAuth2 authorization."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Identify the Yoto account from the access token."""
        try:
            user_id = get_account_id(data["token"]["access_token"])
        except YotoError:
            return self.async_abort(reason="oauth_unauthorized")

        await self.async_set_unique_id(user_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Yoto", data=data)
