"""Config flow for Home Connect."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Home Connect OAuth2 authentication."""

    DOMAIN = DOMAIN

    MINOR_VERSION = 3

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        await self.async_set_unique_id(
            jwt.decode(
                data["token"]["access_token"], options={"verify_signature": False}
            )["sub"]
        )
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            if self.unique_id == reauth_entry.unique_id:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=data
                )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
