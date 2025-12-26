"""Config flow for the Fazilet Takvim integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required("district_id"): int})


class TakvimConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fazilet Takvim."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where the user provides input."""
        if user_input is not None:
            district_id = str(user_input["district_id"])

            # 1. Set unique ID
            await self.async_set_unique_id(district_id)

            # 2. Abort if a config entry with this ID already exists
            self._abort_if_unique_id_configured()

            # 3. Create the config entry
            return self.async_create_entry(
                title=f"Prayer Times ({district_id})", data=user_input
            )

        # Show the form if user_input is None
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
