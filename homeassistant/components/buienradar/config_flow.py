"""Config flow for buienradar integration."""
from __future__ import annotations

import copy
from typing import Any, cast

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_COUNTRY,
    CONF_DELTA,
    CONF_TIMEFRAME,
    DEFAULT_COUNTRY,
    DEFAULT_DELTA,
    DEFAULT_TIMEFRAME,
    DOMAIN,
    SUPPORTED_COUNTRY_CODES,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COUNTRY, default=DEFAULT_COUNTRY): vol.In(
            SUPPORTED_COUNTRY_CODES
        ),
        vol.Optional(CONF_DELTA, default=DEFAULT_DELTA): NumberSelector(
            NumberSelectorConfig(
                min=0,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            ),
        ),
        vol.Optional(CONF_TIMEFRAME, default=DEFAULT_TIMEFRAME): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=120,
                step=5,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="minutes",
            ),
        ),
    }
)


async def _options_suggested_values(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    parent_handler = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    suggested_values = copy.deepcopy(dict(parent_handler.config_entry.data))
    suggested_values.update(parent_handler.options)
    return suggested_values


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA, suggested_values=_options_suggested_values
    ),
}


class BuienradarFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buienradar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            lat = user_input[CONF_LOCATION][CONF_LATITUDE]
            lon = user_input[CONF_LOCATION][CONF_LONGITUDE]

            await self.async_set_unique_id(f"{lat}-{lon}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{lat},{lon}", data={CONF_LATITUDE: lat, CONF_LONGITUDE: lon}
            )
        user_input = {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION,
                    default=user_input.get(
                        CONF_LOCATION,
                        {
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ),
                ): LocationSelector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
