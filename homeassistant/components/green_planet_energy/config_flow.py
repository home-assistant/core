"""Config flow for Green Planet Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({})


class GreenPlanetEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Green Planet Energy."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Green Planet Energy", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
