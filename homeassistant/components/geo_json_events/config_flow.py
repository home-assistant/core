"""Config flow to configure the GeoJSON events integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_URL,
    UnitOfLength,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.util.unit_conversion import DistanceConverter

from .const import DEFAULT_RADIUS_IN_M, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_LOCATION): selector.LocationSelector(
            selector.LocationSelectorConfig(radius=True, icon="")
        ),
    }
)


class GeoJsonEventsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a GeoJSON events config flow."""

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
        location: dict[str, Any] = user_input[CONF_LOCATION]
        latitude: float = location[CONF_LATITUDE]
        longitude: float = location[CONF_LONGITUDE]
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
                    location[CONF_RADIUS],
                    UnitOfLength.METERS,
                    UnitOfLength.KILOMETERS,
                ),
            },
        )
