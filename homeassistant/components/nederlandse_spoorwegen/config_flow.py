"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(config_entries.ConfigFlow, domain="nederlandse_spoorwegen"):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.debug("Initializing NSConfigFlow")
        self._api_key: str | None = None
        self._routes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            masked_api_key = (
                api_key[:3] + "***" + api_key[-2:] if len(api_key) > 5 else "***"
            )
            _LOGGER.debug("User provided API key: %s", masked_api_key)
            # Abort if an entry with this API key already exists
            await self.async_set_unique_id(api_key)
            self._abort_if_unique_id_configured()
            self._api_key = api_key
            return await self.async_step_routes()

        _LOGGER.debug("Showing API key form to user")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the step to add routes."""
        errors: dict[str, str] = {}
        ROUTE_SCHEMA = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("from"): str,
                vol.Required("to"): str,
                vol.Optional("via"): str,
                vol.Optional("time"): str,
            }
        )
        if user_input is not None:
            _LOGGER.debug("User provided route: %s", user_input)
            self._routes.append(user_input)
            # For simplicity, allow adding one route for now, or finish
            return self.async_create_entry(
                title="Nederlandse Spoorwegen",
                data={CONF_API_KEY: self._api_key, "routes": self._routes},
            )
        _LOGGER.debug("Showing route form to user")
        return self.async_show_form(
            step_id="routes", data_schema=ROUTE_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NSOptionsFlowHandler:
        """Return the options flow handler for this config entry."""
        return NSOptionsFlowHandler(config_entry)


class NSOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for Nederlandse Spoorwegen integration."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow handler."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the options flow initialization step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Example: let user edit routes (not implemented in detail here)
        data_schema = vol.Schema({})
        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
