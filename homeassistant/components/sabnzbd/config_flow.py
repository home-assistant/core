"""Adds config flow for SabNzbd."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .helpers import get_client

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
            )
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            )
        ),
    }
)


class SABnzbdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sabnzbd config flow."""

    VERSION = 1

    _existing_entry: ConfigEntry

    async def _async_validate_and_save(
        self, user_input: dict[str, Any] | None, step: str
    ) -> ConfigFlowResult:
        """Validate user input and create/update config entry."""
        errors = {}

        if user_input is not None:
            sab_api = await get_client(self.hass, user_input)
            if not sab_api:
                errors["base"] = "cannot_connect"
            else:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._existing_entry, data_updates=user_input
                    )

                return self.async_create_entry(
                    title=user_input[CONF_API_KEY][:12], data=user_input
                )

        return self.async_show_form(
            step_id=step,
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        self._existing_entry = self._get_reconfigure_entry()
        return await self._async_validate_and_save(user_input, "reconfigure")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self._async_validate_and_save(user_input, "user")
