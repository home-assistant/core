"""Config flow for OneDrive."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from onedrive_personal_sdk.clients.client import OneDriveClient
from onedrive_personal_sdk.exceptions import OneDriveException
from onedrive_personal_sdk.models.items import AppRoot, ItemUpdate
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import (
    CONF_DELETE_PERMANENTLY,
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    DOMAIN,
    OAUTH_SCOPES,
)
from .coordinator import OneDriveConfigEntry

FOLDER_NAME_SCHEMA = vol.Schema({vol.Required(CONF_FOLDER_NAME): str})


class OneDriveConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle OneDrive OAuth2 authentication."""

    DOMAIN = DOMAIN
    MINOR_VERSION = 2

    client: OneDriveClient
    approot: AppRoot

    def __init__(self) -> None:
        """Initialize the OneDrive config flow."""
        super().__init__()
        self.step_data: dict[str, Any] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    @property
    def apps_folder(self) -> str:
        """Return the name of the Apps folder (translated)."""
        return (
            path.split("/")[-1]
            if (path := self.approot.parent_reference.path)
            else "Apps"
        )

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

        if self.source != SOURCE_USER:
            self._abort_if_unique_id_mismatch(
                reason="wrong_drive",
            )

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                entry=reauth_entry,
                data=data,
            )

        if self.source != SOURCE_RECONFIGURE:
            self._abort_if_unique_id_configured()

        self.step_data = data

        if self.source == SOURCE_RECONFIGURE:
            return await self.async_step_reconfigure_folder()

        return await self.async_step_folder_name()

    async def async_step_folder_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask for the folder name."""
        errors: dict[str, str] = {}
        instance_id = await async_get_instance_id(self.hass)
        if user_input is not None:
            try:
                folder = await self.client.create_folder(
                    self.approot.id, user_input[CONF_FOLDER_NAME]
                )
            except OneDriveException:
                self.logger.debug("Failed to create folder", exc_info=True)
                errors["base"] = "folder_creation_error"
            else:
                if folder.description and folder.description != instance_id:
                    errors[CONF_FOLDER_NAME] = "folder_already_in_use"
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
                        CONF_FOLDER_NAME: user_input[CONF_FOLDER_NAME],
                    },
                )

        default_folder_name = (
            f"backups_{instance_id[:8]}"
            if user_input is None
            else user_input[CONF_FOLDER_NAME]
        )

        return self.async_show_form(
            step_id="folder_name",
            data_schema=self.add_suggested_values_to_schema(
                FOLDER_NAME_SCHEMA, {CONF_FOLDER_NAME: default_folder_name}
            ),
            description_placeholders={
                "apps_folder": self.apps_folder,
                "approot": self.approot.name,
            },
            errors=errors,
        )

    async def async_step_reconfigure_folder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the folder name."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            if (
                new_folder_name := user_input[CONF_FOLDER_NAME]
            ) != reconfigure_entry.data[CONF_FOLDER_NAME]:
                try:
                    await self.client.update_drive_item(
                        reconfigure_entry.data[CONF_FOLDER_ID],
                        ItemUpdate(name=new_folder_name),
                    )
                except OneDriveException:
                    self.logger.debug("Failed to update folder", exc_info=True)
                    errors["base"] = "folder_rename_error"
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={**reconfigure_entry.data, CONF_FOLDER_NAME: new_folder_name},
                )

        return self.async_show_form(
            step_id="reconfigure_folder",
            data_schema=self.add_suggested_values_to_schema(
                FOLDER_NAME_SCHEMA,
                {CONF_FOLDER_NAME: reconfigure_entry.data[CONF_FOLDER_NAME]},
            ),
            description_placeholders={
                "apps_folder": self.apps_folder,
                "approot": self.approot.name,
            },
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
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the entry."""
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: OneDriveConfigEntry,
    ) -> OneDriveOptionsFlowHandler:
        """Create the options flow."""
        return OneDriveOptionsFlowHandler()


class OneDriveOptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for OneDrive."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DELETE_PERMANENTLY,
                    default=self.config_entry.options.get(
                        CONF_DELETE_PERMANENTLY, False
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
