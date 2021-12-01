"""Config flow to configure the OpenUV component."""
from __future__ import annotations

from typing import Any

from pyopenuv import Client
from pyopenuv.errors import OpenUvError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
)


class OpenUvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an OpenUV config flow."""

    VERSION = 2

    @property
    def config_schema(self) -> vol.Schema:
        """Return the config schema."""
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Inclusive(
                    CONF_LATITUDE, "coords", default=self.hass.config.latitude
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE, "coords", default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(
                    CONF_ELEVATION, default=self.hass.config.elevation
                ): vol.Coerce(float),
            }
        )

    async def _show_form(self, errors: dict[str, Any] | None = None) -> FlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.config_schema,
            errors=errors if errors else {},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OpenUvOptionsFlowHandler:
        """Define the config flow to handle options."""
        return OpenUvOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(user_input[CONF_API_KEY], 0, 0, session=websession)

        try:
            await client.uv_index()
        except OpenUvError:
            return await self._show_form({CONF_API_KEY: "invalid_api_key"})

        return self.async_create_entry(title=identifier, data=user_input)


class OpenUvOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a OpenUV options flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FROM_WINDOW,
                        description={
                            "suggested_value": self.entry.options.get(
                                CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW
                            )
                        },
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_TO_WINDOW,
                        description={
                            "suggested_value": self.entry.options.get(
                                CONF_FROM_WINDOW, DEFAULT_TO_WINDOW
                            )
                        },
                    ): vol.Coerce(float),
                }
            ),
        )
