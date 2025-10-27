"""Config flow for zeversolar integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    },
)


class ZeverSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zeversolar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # Skip validation - allow configuration even when inverter is offline
        # This enables setup during night time when inverter is naturally offline
        _LOGGER.info("Configuring Zeversolar integration for host: %s (no validation)", user_input[CONF_HOST])
        
        # Use host as unique ID since we can't get serial number when offline
        await self.async_set_unique_id(f"zeversolar_{user_input[CONF_HOST]}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(title="Zeversolar", data=user_input)
