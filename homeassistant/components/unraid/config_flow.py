"""Config flow for KAT Bulgaria integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST

from .const import DOMAIN
from .unraid_client import UnraidClient

_LOGGER = logging.getLogger(__name__)

CONFIG_FLOW_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for unraid."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        # If no Input
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA
            )

        # Init user input values & init KatClient
        unraid_host = user_input[CONF_HOST]
        unraid_apikey = user_input[CONF_API_KEY]

        # Verify user input
        try:
            unraid_client = UnraidClient(self.hass, unraid_host, unraid_apikey)
            await unraid_client.query_data()
        except httpx.RequestError as e:
            _LOGGER.error("An error occurred while requesting: %s", e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA, errors=errors
            )
        except httpx.HTTPStatusError as e:
            _LOGGER.error(
                "HTTP error occurred: %s - %s", e.response.status_code, e.response.text
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA, errors=errors
            )

        # If this person (EGN) is already configured, abort
        await self.async_set_unique_id(unraid_host)
        self._abort_if_unique_id_configured()

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_FLOW_DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(title=f"Unraid - {unraid_host}", data=user_input)
