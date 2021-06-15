"""Config flow for Forecast Solar integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    DOMAIN,
)


class ForecastSolarFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast Solar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(CONF_DECLINATION, default=0): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=90)
                    ),
                    vol.Optional(CONF_AZIMUTH, default=0): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=360)
                    ),
                    vol.Required(CONF_MODULES_POWER): vol.Coerce(int),
                }
            ),
        )


class ForecastSolarOptionFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
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
                        CONF_DECLINATION,
                        default=self.entry.options.get(
                            CONF_DECLINATION, self.entry.data[CONF_DECLINATION]
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                    vol.Optional(
                        CONF_AZIMUTH,
                        default=self.entry.options.get(
                            CONF_AZIMUTH, self.entry.data[CONF_AZIMUTH]
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=-0, max=360)),
                    vol.Required(
                        CONF_MODULES_POWER,
                        default=self.entry.options.get(
                            CONF_MODULES_POWER, self.entry.data[CONF_MODULES_POWER]
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_DAMPING,
                        default=self.entry.options.get(
                            CONF_DAMPING, self.entry.data.get(CONF_DAMPING, 0)
                        ),
                    ): vol.Coerce(float),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
