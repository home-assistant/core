"""Config flow for Bosch Smart Home Camera."""

from collections.abc import Mapping
import logging
from typing import Any, override

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    list_cameras,
)
import jwt
import probatio

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .application_credentials import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
from .const import DOMAIN

MAX_ACCOUNT_ID_LENGTH = 128


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
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Inform the user that reauthentication is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=probatio.Schema({})
            )
        return await self.async_step_user(
            {"implementation": self._get_reauth_entry().data["auth_implementation"]}
        )

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create the entry, or update the existing one during reauth."""
        try:
            # The token comes straight from the token endpoint over TLS, so only
            # the subject is read and the signature is not verified again.
            account_id = jwt.decode(
                data["token"]["access_token"], options={"verify_signature": False}
            )["sub"]
        except jwt.InvalidTokenError, KeyError:
            return self.async_abort(reason="oauth_error")
        if (
            not isinstance(account_id, str)
            or not account_id.strip()
            or len(account_id) > MAX_ACCOUNT_ID_LENGTH
        ):
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(account_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
        else:
            self._abort_if_unique_id_configured()
        try:
            await list_cameras(
                async_get_clientsession(self.hass), data["token"]["access_token"]
            )
        except BoschCameraAuthError:
            return self.async_abort(reason="invalid_auth")
        except BoschCameraConnectionError, BoschCameraInvalidResponseError:
            return self.async_abort(reason="cannot_connect")
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        return await super().async_oauth_create_entry(data)
