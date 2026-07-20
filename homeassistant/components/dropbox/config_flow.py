"""Config flow for Dropbox."""

from collections.abc import Mapping
import logging
from typing import Any, override

from python_dropbox_api import DropboxAPIClient

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .auth import DropboxConfigFlowAuth
from .const import DOMAIN, OAUTH2_SCOPES


class DropboxConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Dropbox OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "token_access_type": "offline",
            "scope": " ".join(OAUTH2_SCOPES),
        }

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]

        auth = DropboxConfigFlowAuth(async_get_clientsession(self.hass), access_token)

        client = DropboxAPIClient(auth)
        account_info = await client.get_account_info()

        await self.async_set_unique_id(account_info.account_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=account_info.email, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        token = entry_data[CONF_TOKEN]
        if not set(token.get("scope", "").split()).issuperset(OAUTH2_SCOPES):
            return await self.async_step_reauth_permissions()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_reauth_permissions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that additional permissions are required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_permissions")
        return await self.async_step_user()
