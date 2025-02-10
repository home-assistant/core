"""Config flow for OneDrive."""

from collections.abc import Mapping
import logging
from typing import Any, cast

from onedrive_personal_sdk.clients.client import OneDriveClient
from onedrive_personal_sdk.exceptions import OneDriveException
from onedrive_personal_sdk.models.items import ItemUpdate
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import CONF_FOLDER_NAME, DOMAIN, OAUTH_SCOPES
from .coordinator import OneDriveConfigEntry


class OneDriveConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle OneDrive OAuth2 authentication."""

    DOMAIN = DOMAIN
    MINOR_VERSION = 2

    step_data: dict[str, Any] = {}
    title: str

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        async def get_access_token() -> str:
            return cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])

        graph_client = OneDriveClient(
            get_access_token, async_get_clientsession(self.hass)
        )

        try:
            approot = await graph_client.get_approot()
        except OneDriveException:
            self.logger.exception("Failed to connect to OneDrive")
            return self.async_abort(reason="connection_error")
        except Exception:
            self.logger.exception("Unknown error")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(approot.parent_reference.drive_id)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_drive",
            )
            return self.async_update_reload_and_abort(
                entry=reauth_entry,
                data=data,
            )

        self._abort_if_unique_id_configured()

        self.title = (
            f"{approot.created_by.user.display_name}'s OneDrive"
            if approot.created_by.user and approot.created_by.user.display_name
            else "OneDrive"
        )
        self.step_data = data
        return await self.async_step_folder_name()

    async def async_step_folder_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to ask for the folder name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self.source == SOURCE_RECONFIGURE:
                reconfigure_entry: OneDriveConfigEntry = self._get_reconfigure_entry()
                if (old_name := reconfigure_entry.data[CONF_FOLDER_NAME]) != (
                    new_name := user_input[CONF_FOLDER_NAME]
                ):
                    self.logger.debug(
                        "Renaming folder from %s to %s", old_name, new_name
                    )
                    client = reconfigure_entry.runtime_data.client
                    try:
                        approot = await client.get_approot()
                        await client.update_drive_item(
                            f"{approot.id}:/{old_name}", ItemUpdate(name=new_name)
                        )
                    except OneDriveException:
                        errors["base"] = "update_error"
                if not errors:
                    return self.async_update_reload_and_abort(
                        entry=reconfigure_entry,
                        data={**reconfigure_entry.data, **user_input},
                    )
            else:
                return self.async_create_entry(
                    title=self.title, data={**self.step_data, **user_input}
                )

        instance_id = await async_get_instance_id(self.hass)
        default_folder_name = f"backups_{instance_id[:8]}"
        return self.async_show_form(
            step_id="folder_name",
            data_schema=vol.Schema(
                {vol.Required(CONF_FOLDER_NAME, default=default_folder_name): str},
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
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the entry."""
        return await self.async_step_folder_name()
