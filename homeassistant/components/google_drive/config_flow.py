"""Config flow for the Google Drive integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from google_drive_api.exceptions import GoogleDriveApiError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AsyncConfigFlowAuth, DriveClient
from .const import DOMAIN

DEFAULT_NAME = "Google Drive"
DRIVE_FOLDER_URL_PREFIX = "https://drive.google.com/drive/folders/"
OAUTH2_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Drive OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        client = DriveClient(
            await instance_id.async_get(self.hass),
            AsyncConfigFlowAuth(
                async_get_clientsession(self.hass), data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            ),
        )

        try:
            email_address = await client.async_get_email_address()
        except GoogleDriveApiError as err:
            self.logger.error("Error getting email address: %s", err)
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": str(err)},
            )
        except Exception:
            self.logger.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(email_address)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_account",
                description_placeholders={"email": cast(str, reauth_entry.unique_id)},
            )
            return self.async_update_reload_and_abort(reauth_entry, data=data)

        self._abort_if_unique_id_configured()

        try:
            (
                folder_id,
                folder_name,
            ) = await client.async_create_ha_root_folder_if_not_exists()
        except GoogleDriveApiError as err:
            self.logger.error("Error creating folder: %s", str(err))
            return self.async_abort(
                reason="create_folder_failure",
                description_placeholders={"message": str(err)},
            )

        return self.async_create_entry(
            title=DEFAULT_NAME,
            data=data,
            description_placeholders={
                "folder_name": folder_name,
                "url": f"{DRIVE_FOLDER_URL_PREFIX}{folder_id}",
            },
        )
