"""Config Flow for Tesla Fleet integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import jwt

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, LOGGER
from .oauth import TeslaSystemImplementation


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Tesla Fleet API OAuth2 authentication."""

    DOMAIN = DOMAIN
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        self.async_register_implementation(
            self.hass,
            TeslaSystemImplementation(self.hass),
        )

        return await super().async_step_user()

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )
        uid = token["sub"]

        if not self.reauth_entry:
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=uid, data=data)

        if self.reauth_entry.unique_id == uid:
            self.hass.config_entries.async_update_entry(
                self.reauth_entry,
                data=data,
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_abort(
            reason="reauth_account_mismatch",
            description_placeholders={"title": self.reauth_entry.title},
        )

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
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"name": "Tesla Fleet"},
            )
        return await self.async_step_user()
