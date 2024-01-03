"""Config flow for WeatherflowCloud integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol
from weatherflow4py.api import WeatherFlowRestAPI

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlowCloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_TOKEN])
            self._abort_if_unique_id_configured()

            # Validate Entry
            api_token = user_input[CONF_API_TOKEN]
            try:
                async with WeatherFlowRestAPI(api_token) as api:
                    await api.async_get_stations()
            except ClientResponseError as err:
                if err.status == 401:
                    errors["base"] = "invalid_api_key"
                else:
                    errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Weatherflow REST",
                    data={CONF_API_TOKEN: api_token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
