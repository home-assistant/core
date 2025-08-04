"""Config flow for Green Planet Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({})


async def prepare_config_entry(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Prepare the config entry for Green Planet Energy.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # For this integration, no API validation is required
    # as the API might require authentication or not be publicly accessible
    _LOGGER.info("Green Planet Energy integration setup - skipping API validation")
    return {"title": "Green Planet Energy"}


class GreenPlanetEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Green Planet Energy."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Check if integration is already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await prepare_config_entry(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
