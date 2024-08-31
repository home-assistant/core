"""Config flow for WeatherflowCloud integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol
from weatherflow4py.api import WeatherFlowRestAPI

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import DOMAIN


async def _validate_api_token(api_token: str) -> dict[str, Any]:
    """Validate the API token."""
    try:
        async with WeatherFlowRestAPI(api_token) as api:
            await api.async_get_stations()
    except ClientResponseError as err:
        if err.status == 401:
            return {"base": "invalid_api_key"}
        return {"base": "cannot_connect"}
    return {}


class WeatherFlowCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlowCloud."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow for reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by reauthentication."""
        errors = {}

        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]
            errors = await _validate_api_token(api_token)
            if not errors:
                # Update the existing entry and abort
                if existing_entry := self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                ):
                    return self.async_update_reload_and_abort(
                        existing_entry,
                        data={CONF_API_TOKEN: api_token},
                        reason="reauth_successful",
                        reload_even_if_entry_is_unchanged=False,
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            api_token = user_input[CONF_API_TOKEN]
            errors = await _validate_api_token(api_token)
            if not errors:
                return self.async_create_entry(
                    title="Weatherflow REST",
                    data={CONF_API_TOKEN: api_token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
