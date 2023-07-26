"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from typing import Any

from hydrawiser import core as hydrawiser_core
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup."""
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            try:
                api = await self.hass.async_add_executor_job(
                    hydrawiser_core.Hydrawiser, api_key
                )
            except (ConnectTimeout, HTTPError) as ex:
                LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
                errors["base"] = "unknown"
            else:
                if api.status:
                    await self.async_set_unique_id(f"hydrawise-{api.customer_id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Hydrawise", data=user_input)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import data from YAML."""
        self._async_abort_entries_match(import_data)
        return await self.async_step_user(import_data)
