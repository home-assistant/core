"""Config flow to configure the GeoNet NZ Volcano integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IMPERIAL_UNITS,
    METRIC_UNITS,
)


@callback
def configured_instances(hass):
    """Return a set of configured GeoNet NZ Volcano instances."""
    return {
        f"{entry.data[CONF_LATITUDE]}, {entry.data[CONF_LONGITUDE]}"
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class GeonetnzVolcanoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a GeoNet NZ Volcano config flow."""

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors or {}
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        user_input[CONF_LATITUDE] = latitude
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        user_input[CONF_LONGITUDE] = longitude

        identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        if identifier in configured_instances(self.hass):
            return await self._show_form({"base": "already_configured"})

        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            user_input[CONF_UNIT_SYSTEM] = IMPERIAL_UNITS
        else:
            user_input[CONF_UNIT_SYSTEM] = METRIC_UNITS

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

        return self.async_create_entry(title=identifier, data=user_input)
