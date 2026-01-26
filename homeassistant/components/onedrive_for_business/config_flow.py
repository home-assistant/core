"""Config flow for OneDrive for Business."""

from __future__ import annotations

import logging
from typing import Any, cast

from onedrive_personal_sdk.clients.client import OneDriveClient
from onedrive_personal_sdk.exceptions import OneDriveException
from onedrive_personal_sdk.models.items import AppRoot
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_FOLDER_ID, CONF_FOLDER_PATH, DOMAIN, OAUTH_SCOPES

FOLDER_NAME_SCHEMA = vol.Schema({vol.Required(CONF_FOLDER_PATH): str})


class OneDriveForBusinessConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle OneDrive OAuth2 authentication."""

    DOMAIN = DOMAIN

    client: OneDriveClient
    approot: AppRoot

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    def __init__(self) -> None:
        """Initialize the OneDrive config flow."""
        super().__init__()
        self.step_data: dict[str, Any] = {}  # will contain "auth_implementation"

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        async def get_access_token() -> str:
            return cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])

        self.client = OneDriveClient(
            get_access_token, async_get_clientsession(self.hass)
        )

        try:
            self.approot = await self.client.get_approot()
        except OneDriveException:
            self.logger.exception("Failed to connect to OneDrive")
            return self.async_abort(reason="connection_error")
        except Exception:
            self.logger.exception("Unknown error")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(self.approot.parent_reference.drive_id)
        self._abort_if_unique_id_configured()

        self.step_data = data

        return await self.async_step_select_folder()

    async def async_step_select_folder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask for the folder name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                folder = await self.client.create_folder(
                    "root", user_input[CONF_FOLDER_PATH]
                )
            except OneDriveException:
                self.logger.debug("Failed to create folder", exc_info=True)
                errors["base"] = "folder_creation_error"
            if not errors:
                title = (
                    f"{self.approot.created_by.user.display_name}'s OneDrive"
                    if self.approot.created_by.user
                    and self.approot.created_by.user.display_name
                    else "OneDrive"
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        **self.step_data,
                        CONF_FOLDER_ID: folder.id,
                        CONF_FOLDER_PATH: user_input[CONF_FOLDER_PATH],
                    },
                )

        return self.async_show_form(
            step_id="select_folder",
            data_schema=FOLDER_NAME_SCHEMA,
            errors=errors,
        )
