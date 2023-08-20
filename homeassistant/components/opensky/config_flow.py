"""Config flow for OpenSky integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_RADIUS
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_NAME, DOMAIN
from .sensor import CONF_ALTITUDE, DEFAULT_ALTITUDE


class OpenSkyConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                },
                options={
                    CONF_RADIUS: user_input[CONF_RADIUS],
                    CONF_ALTITUDE: user_input[CONF_ALTITUDE],
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_RADIUS): vol.Coerce(float),
                        vol.Required(CONF_LATITUDE): cv.latitude,
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                        vol.Optional(CONF_ALTITUDE): vol.Coerce(float),
                    }
                ),
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_ALTITUDE: DEFAULT_ALTITUDE,
                },
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        entry_data = {
            CONF_LATITUDE: import_config.get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: import_config.get(
                CONF_LONGITUDE, self.hass.config.longitude
            ),
        }
        self._async_abort_entries_match(entry_data)
        return self.async_create_entry(
            title=import_config.get(CONF_NAME, DEFAULT_NAME),
            data=entry_data,
            options={
                CONF_RADIUS: import_config[CONF_RADIUS] * 1000,
                CONF_ALTITUDE: import_config.get(CONF_ALTITUDE, DEFAULT_ALTITUDE),
            },
        )
