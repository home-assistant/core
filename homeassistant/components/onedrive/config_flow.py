"""Config flow for OneDrive."""

from collections.abc import Mapping
import logging
from typing import Any, cast

from onedrive_personal_sdk.clients.client import OneDriveClient
from onedrive_personal_sdk.exceptions import OneDriveException

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import DOMAIN, OAUTH_SCOPES


class OneDriveConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
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

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        token_provider = OneDriveConfigFlowAccessTokenProvider(
            cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        )

        graph_client = OneDriveClient(
            token_provider, async_get_clientsession(self.hass)
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

        title = (
            f"{approot.created_by.user.display_name}'s OneDrive"
            if approot.created_by.user
            else "OneDrive"
        )
        return self.async_create_entry(title=title, data=data)

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
