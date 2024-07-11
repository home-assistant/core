"""Config flow for Google Mail integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from . import GoogleMailConfigEntry
from .const import DEFAULT_ACCESS, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Mail OAuth2 authentication."""

    DOMAIN = DOMAIN

    reauth_entry: GoogleMailConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(DEFAULT_ACCESS),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
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

        def _get_profile() -> str:
            """Get profile from inside the executor."""
            users = build("gmail", "v1", credentials=credentials).users()
            return users.getProfile(userId="me").execute()["emailAddress"]

        credentials = Credentials(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        email = await self.hass.async_add_executor_job(_get_profile)

        if not self.reauth_entry:
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=email, data=data)

        if self.reauth_entry.unique_id == email:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_abort(
            reason="wrong_account",
            description_placeholders={"email": cast(str, self.reauth_entry.unique_id)},
        )
