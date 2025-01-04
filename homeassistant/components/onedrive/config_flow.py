"""Config flow for OneDrive."""

import logging
from typing import Any

from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.models.drive import Drive
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import CONF_BACKUP_FOLDER, CONF_DRIVE_ID, DOMAIN, OAUTH_SCOPES


class OneDriveConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle OneDrive OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    def __init__(self) -> None:
        """Initialize OneDriveConfigFlow."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._drives: list[Drive] | None = None

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        auth_provider = BaseBearerTokenAuthenticationProvider(
            access_token_provider=OneDriveConfigFlowAccessTokenProvider(
                data[CONF_TOKEN]
            )
        )
        adapter = GraphRequestAdapter(
            auth_provider=auth_provider,
            client=get_async_client(self.hass),
        )

        graph_client = GraphServiceClient(
            request_adapter=adapter,
            scopes=OAUTH_SCOPES,
        )

        self._data = data
        try:
            drives = await graph_client.drives.get()
        except Exception:  # noqa: BLE001
            self.async_abort(reason="connection_error")
        if not drives or not drives.value:
            self.async_abort(reason="no_drives")

        if len(drives.value) == 1:
            await self.async_set_unique_id(drives.value[0].id)
            self._abort_if_unique_id_configured()
            return await self.async_step_folder_selection()

        self._drives = drives.value
        return await self.async_step_drive_selection()

    async def async_step_drive_selection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user pick a drive."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DRIVE_ID])
            self._abort_if_unique_id_configured()
            return await self.async_step_folder_selection()

        drive_options = [
            SelectOptionDict(
                value=drive.id,
                label=f"{drive.name}",
            )
            for drive in self._drives
        ]
        drive_selection_schema = (
            vol.Schema(
                {
                    vol.Required(
                        CONF_DRIVE_ID,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=drive_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_BACKUP_FOLDER, default="/homeassistant/backups"
                    ): str,
                }
            ),
        )

        return self.async_show_form(
            step_id="drive_selection",
            data_schema=drive_selection_schema,
        )

    async def async_step_folder_selection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user pick a folder."""
        if user_input is not None:
            return self.async_create_entry(
                title=DOMAIN, data={**self._data, **user_input}
            )

        return self.async_show_form(
            step_id="drive_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BACKUP_FOLDER, default="/homeassistant/backups"
                    ): str,
                }
            ),
        )
