"""Config flow for the Google Drive integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiogoogle import Aiogoogle
from aiogoogle.excs import AiogoogleError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .api import convert_to_user_creds
from .const import DEFAULT_NAME, DOMAIN, DRIVE_FOLDER_URL_PREFIX, OAUTH2_SCOPES


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

        user_creds = convert_to_user_creds(token=data[CONF_TOKEN])

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            async with Aiogoogle(user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover("drive", "v3")
                try:
                    await aiogoogle.as_user(
                        drive_v3.files.get(fileId=reauth_entry.unique_id, fields="")
                    )
                except AiogoogleError as err:
                    self.logger.error(
                        "Could not find folder '%s%s': %s",
                        DRIVE_FOLDER_URL_PREFIX,
                        reauth_entry.unique_id,
                        str(err),
                    )
                    return self.async_abort(reason="get_folder_failure")
            return self.async_update_reload_and_abort(reauth_entry, data=data)

        async with Aiogoogle(user_creds=user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            req = drive_v3.files.create(
                fields="id",
                json={
                    "name": "Home Assistant",
                    "mimeType": "application/vnd.google-apps.folder",
                    # Adding a property to be able to identify this folder
                    # if needed in the future.
                    # 1 instead of true to avoid hitting char limits
                    # if we ever need to add more properties.
                    "properties": {"ha_root": "1"},
                },
            )
            try:
                res = await aiogoogle.as_user(req)
            except AiogoogleError as err:
                self.logger.error("Error creating folder: %s", str(err))
                return self.async_abort(reason="create_folder_failure")
        folder_id = res["id"]
        await self.async_set_unique_id(folder_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data=data,
            description_placeholders={"url": f"{DRIVE_FOLDER_URL_PREFIX}{folder_id}"},
        )
