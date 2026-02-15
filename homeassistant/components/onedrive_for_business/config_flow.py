"""Config flow for OneDrive for Business."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from onedrive_personal_sdk.clients.client import OneDriveClient
from onedrive_personal_sdk.exceptions import OneDriveException
from onedrive_personal_sdk.models.items import AppRoot
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .application_credentials import tenant_id_context
from .const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
    CONF_TENANT_ID,
    DOMAIN,
    OAUTH_SCOPES,
)

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
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_pick_tenant()

    async def async_step_pick_tenant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the tenant id."""
        if user_input is not None:
            self._data[CONF_TENANT_ID] = user_input[CONF_TENANT_ID]
            # Continue with OAuth flow using tenant context
            with tenant_id_context(user_input[CONF_TENANT_ID]):
                return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="pick_tenant",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TENANT_ID): str,
                }
            ),
            description_placeholders={
                "entra_url": "https://entra.microsoft.com/",
                "redirect_url": "https://my.home-assistant.io/redirect/oauth",
            },
        )

    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pick implementation step with tenant context."""
        with tenant_id_context(self._data[CONF_TENANT_ID]):
            return await super().async_step_pick_implementation(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the initial step."""

        async def get_access_token() -> str:
            return cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])

        self.client = OneDriveClient(
            get_access_token, async_get_clientsession(self.hass)
        )

        try:
            self.approot = await self.client.get_approot()
            drive = await self.client.get_drive()
        except OneDriveException:
            self.logger.exception("Failed to connect to OneDrive")
            return self.async_abort(reason="connection_error")
        except Exception:
            self.logger.exception("Unknown error")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(drive.id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_drive")
            return self.async_update_reload_and_abort(
                entry=self._get_reauth_entry(),
                data_updates=data,
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="wrong_drive")
        else:
            self._abort_if_unique_id_configured()

        self._data.update(data)

        if self.source == SOURCE_RECONFIGURE:
            return await self.async_step_reconfigure_folder()

        return await self.async_step_select_folder()

    async def async_step_select_folder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask for the folder name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                path = str(user_input[CONF_FOLDER_PATH]).lstrip("/")
                folder = await self.client.create_folder("root", path)
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
                        **self._data,
                        CONF_FOLDER_ID: folder.id,
                        CONF_FOLDER_PATH: user_input[CONF_FOLDER_PATH],
                    },
                )

        return self.async_show_form(
            step_id="select_folder",
            data_schema=FOLDER_NAME_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the entry."""
        self._data[CONF_TENANT_ID] = self._get_reconfigure_entry().data[CONF_TENANT_ID]
        with tenant_id_context(self._data[CONF_TENANT_ID]):
            return await self.async_step_pick_implementation()

    async def async_step_reconfigure_folder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask for new folder path during reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            path = str(user_input[CONF_FOLDER_PATH]).lstrip("/")
            try:
                folder = await self.client.create_folder("root", path)
            except OneDriveException:
                self.logger.debug("Failed to create folder", exc_info=True)
                errors["base"] = "folder_creation_error"
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        **self._data,
                        CONF_FOLDER_ID: folder.id,
                        CONF_FOLDER_PATH: user_input[CONF_FOLDER_PATH],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure_folder",
            data_schema=self.add_suggested_values_to_schema(
                FOLDER_NAME_SCHEMA,
                {CONF_FOLDER_PATH: reconfigure_entry.data[CONF_FOLDER_PATH]},
            ),
            errors=errors,
        )

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
        self._data[CONF_TENANT_ID] = self._get_reauth_entry().data[CONF_TENANT_ID]
        with tenant_id_context(self._data[CONF_TENANT_ID]):
            return await self.async_step_pick_implementation()
