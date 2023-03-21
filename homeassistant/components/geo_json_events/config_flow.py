"""Config flow to configure the GeoJSON events integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_RADIUS_IN_KM, DEFAULT_SCAN_INTERVAL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
        vol.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    }
)

_LOGGER = logging.getLogger(__name__)


class GeoJsonEventsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a GeoJSON events config flow."""

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        legacy_scan_interval = import_config.get(CONF_SCAN_INTERVAL, None)
        # Convert scan interval because it now has to be in seconds.
        if legacy_scan_interval and isinstance(legacy_scan_interval, timedelta):
            import_config[CONF_SCAN_INTERVAL] = legacy_scan_interval.total_seconds()
        identifier = f"{import_config[CONF_URL]}, {import_config.get(CONF_LATITUDE, self.hass.config.latitude)}, {import_config.get(CONF_LONGITUDE, self.hass.config.longitude)}"
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=identifier, data=import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        _LOGGER.debug("User input: %s", user_input)
        if not user_input:
            suggested_values: Mapping[str, Any] = {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            }
            data_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA, suggested_values
            )
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        user_input[CONF_LATITUDE] = latitude
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        user_input[CONF_LONGITUDE] = longitude

        identifier = f"{user_input[CONF_URL]}, {latitude}, {longitude}"
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval

        return self.async_create_entry(title=identifier, data=user_input)
