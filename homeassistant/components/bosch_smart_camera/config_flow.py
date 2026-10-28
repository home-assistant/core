"""Config flow for Bosch Smart Camera."""

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
from homeassistant.config_entries import ConfigFlowResult
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

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create the entry after checking the camera API accepts the token."""
        access_token = data["token"]["access_token"]
        try:
            account_id = account_id_from_token(access_token)
        except BoschCameraAuthError:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(account_id)
        self._abort_if_unique_id_configured()
        try:
            await list_cameras(async_get_clientsession(self.hass), access_token)
        except BoschCameraAuthError:
            return self.async_abort(reason="invalid_auth")
        except BoschCameraConnectionError, BoschCameraInvalidResponseError:
            return self.async_abort(reason="cannot_connect")
        return await super().async_oauth_create_entry(data)
