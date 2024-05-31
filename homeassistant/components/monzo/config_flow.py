"""Config flow for Monzo."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class MonzoFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow."""

    DOMAIN = DOMAIN

    oauth_data: dict[str, Any]

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_await_approval_confirmation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to confirm in-app approval."""
        if user_input is not None:
            return self.async_create_entry(title=DOMAIN, data={**self.oauth_data})

        data_schema = vol.Schema({vol.Required("confirm"): bool})

        return self.async_show_form(
            step_id="await_approval_confirmation", data_schema=data_schema
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        user_id = str(data[CONF_TOKEN]["user_id"])
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()

        self.oauth_data = data

        return await self.async_step_await_approval_confirmation()
