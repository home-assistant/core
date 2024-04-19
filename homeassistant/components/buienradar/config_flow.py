"""Config flow for buienradar integration."""

from __future__ import annotations

import copy
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY_CODE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_DELTA,
    CONF_FORECAST_DAYS,
    CONF_TIMEFRAME,
    DEFAULT_COUNTRY,
    DEFAULT_DELTA,
    DEFAULT_TIMEFRAME,
    DOMAIN,
    SUPPORTED_COUNTRY_CODES,
)

FORECAST_OPTIONS = vol.Schema(
    {
        vol.Required(CONF_FORECAST_DAYS, default=["now"]): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    "now",
                    "1d",
                    "2d",
                    "3d",
                    "4d",
                    "5d",
                ],
                multiple=True,
                mode=selector.SelectSelectorMode("list"),
                translation_key="forecast_days",
            )
        )
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_COUNTRY_CODE, default=DEFAULT_COUNTRY
        ): selector.CountrySelector(
            selector.CountrySelectorConfig(countries=SUPPORTED_COUNTRY_CODES)
        ),
        vol.Optional(CONF_DELTA, default=DEFAULT_DELTA): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            ),
        ),
        vol.Optional(
            CONF_TIMEFRAME, default=DEFAULT_TIMEFRAME
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5,
                max=120,
                step=5,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="minutes",
            ),
        ),
    }
).extend(FORECAST_OPTIONS.schema)


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


class BuienradarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buienradar."""

    VERSION = 1

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self.config: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)

            await self.async_set_unique_id(f"{lat}-{lon}")
            self._abort_if_unique_id_configured()

            self.config.update(user_input)
            return await self.async_step_forecasts()

            #

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors={},
        )

    async def async_step_forecasts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow to select enabled forecast days."""
        if user_input is not None:
            lat = self.config.get(CONF_LATITUDE)
            lon = self.config.get(CONF_LONGITUDE)

            return self.async_create_entry(
                title=f"{lat},{lon}",
                data={
                    CONF_LATITUDE: self.config.get(CONF_LATITUDE),
                    CONF_LONGITUDE: self.config.get(CONF_LONGITUDE),
                },
                options={CONF_FORECAST_DAYS: user_input.get(CONF_FORECAST_DAYS)},
            )

        return self.async_show_form(
            step_id="forecasts", data_schema=FORECAST_OPTIONS, errors={}
        )
