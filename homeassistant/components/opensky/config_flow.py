"""Config flow for OpenSky integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_NAME, DEFAULT_RADIUS, DOMAIN
from .sensor import CONF_ALTITUDE, DEFAULT_ALTITUDE

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_LOCATION): LocationSelector(
            config=LocationSelectorConfig(radius=True)
        ),
        vol.Optional(CONF_ALTITUDE): vol.Coerce(float),
    }
)


class OpenSkyConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={},
                options={
                    CONF_LOCATION: user_input[CONF_LOCATION],
                    CONF_ALTITUDE: user_input.get(CONF_ALTITUDE, DEFAULT_ALTITUDE),
                },
            )
        form_data: dict[str, Any] = {
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
                CONF_RADIUS: DEFAULT_RADIUS,
            },
            CONF_ALTITUDE: DEFAULT_ALTITUDE,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, form_data),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        latitude = import_config.get(CONF_LATITUDE, self.hass.config.latitude)
        longitude = import_config.get(CONF_LONGITUDE, self.hass.config.longitude)
        for entry in self._async_current_entries():
            if (
                entry.options[CONF_LOCATION][CONF_LATITUDE] == latitude
                and entry.options[CONF_LOCATION][CONF_LONGITUDE] == longitude
            ):
                return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=import_config.get(CONF_NAME, DEFAULT_NAME),
            data={},
            options={
                CONF_LOCATION: {
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_RADIUS: import_config[CONF_RADIUS] * 1000,
                },
                CONF_ALTITUDE: import_config.get(CONF_ALTITUDE, DEFAULT_ALTITUDE),
            },
        )
