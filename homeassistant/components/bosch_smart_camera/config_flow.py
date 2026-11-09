"""Config flow for Bosch Smart Camera."""

from collections.abc import Mapping
import logging
from typing import Any, override

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    account_id_from_token,
    list_cameras,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .application_credentials import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
from .const import DOMAIN


class BoschCameraFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow handling Bosch SingleKey ID OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(
                OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Bosch SingleKey ID"
            ),
        )
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to sign in again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create the entry after checking the camera API accepts the token."""
        access_token = data["token"]["access_token"]
        try:
            account_id = account_id_from_token(access_token)
        except BoschCameraAuthError:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(account_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
        else:
            self._abort_if_unique_id_configured()
        try:
            await list_cameras(async_get_clientsession(self.hass), access_token)
        except BoschCameraAuthError:
            return self.async_abort(reason="invalid_auth")
        except BoschCameraConnectionError, BoschCameraInvalidResponseError:
            return self.async_abort(reason="cannot_connect")
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        return await super().async_oauth_create_entry(data)
