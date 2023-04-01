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
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    UnitOfLength,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    DEFAULT_RADIUS_IN_KM,
    DEFAULT_RADIUS_IN_M,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_LOCATION): selector.LocationSelector(
            selector.LocationSelectorConfig(radius=True, icon="")
        ),
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
        url: str = import_config[CONF_URL]
        latitude: float | None = import_config.get(
            CONF_LATITUDE, self.hass.config.latitude
        )
        longitude: float | None = import_config.get(
            CONF_LONGITUDE, self.hass.config.longitude
        )
        self._async_abort_entries_match(
            {
                CONF_URL: url,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
            }
        )
        return self.async_create_entry(
            title=f"{url} ({latitude}, {longitude})",
            data={
                CONF_URL: url,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: import_config.get(CONF_RADIUS, DEFAULT_RADIUS_IN_KM),
                CONF_SCAN_INTERVAL: import_config.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            suggested_values: Mapping[str, Any] = {
                CONF_LOCATION: {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_RADIUS: DEFAULT_RADIUS_IN_M,
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA, suggested_values
            )
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        url: str = user_input[CONF_URL]
        latitude: float | None = user_input.get(CONF_LOCATION, {}).get(CONF_LATITUDE)
        longitude: float | None = user_input.get(CONF_LOCATION, {}).get(CONF_LONGITUDE)
        self._async_abort_entries_match(
            {
                CONF_URL: url,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
            }
        )
        return self.async_create_entry(
            title=f"{url} ({latitude}, {longitude})",
            data={
                CONF_URL: url,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: DistanceConverter.convert(
                    user_input.get(CONF_LOCATION, {}).get(
                        CONF_RADIUS, DEFAULT_RADIUS_IN_M
                    ),
                    UnitOfLength.METERS,
                    UnitOfLength.KILOMETERS,
                ),
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            },
        )
