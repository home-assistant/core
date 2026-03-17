"""Config flow for the Photoptimizer integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import selector

from .const import (
    CONF_AZIMUTH,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_EFFICIENCY_ROUND_TRIP,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_RESERVE_PERCENT,
    CONF_CURRENT_CONSUMPTION_ENTITY,
    CONF_CURRENT_SOLAR_PRODUCTION_ENTITY,
    CONF_DECLINATION,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_EMHASS_TOKEN,
    CONF_EMHASS_URL,
    CONF_GRID_POWER_ENTITY,
    CONF_HORIZON_HOURS,
    CONF_KWP,
    CONF_LOAD_FORECAST_ENTITY,
    CONF_PRICE_INCLUDE_VAT,
    CONF_PV_FORECAST_ENTITY,
    CONF_RESOLUTION,
    CONF_WEAR_COST_PER_KWH,
    DEFAULT_BATTERY_EFFICIENCY_ROUND_TRIP,
    DEFAULT_BATTERY_SOC_RESERVE_PERCENT,
    DEFAULT_EMHASS_URL,
    DEFAULT_HORIZON_HOURS,
    DEFAULT_PRICE_INCLUDE_VAT,
    DEFAULT_RESOLUTION,
    DEFAULT_WEAR_COST_PER_KWH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PhotoptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Photoptimizer config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initial step: use baked-in defaults and continue."""
        self._data[CONF_HORIZON_HOURS] = DEFAULT_HORIZON_HOURS
        self._data[CONF_RESOLUTION] = DEFAULT_RESOLUTION
        return await self.async_step_electricity_price()

    async def async_step_electricity_price(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle electricity price configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            _LOGGER.debug("Electricity price step")

            return await self.async_step_pv_forecast()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ELECTRICITY_PRICE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
                vol.Required(
                    CONF_PRICE_INCLUDE_VAT, default=DEFAULT_PRICE_INCLUDE_VAT
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="electricity_price",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_pv_forecast(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """PV forecast step: either use entity or built-in Forecast.Solar."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            _LOGGER.debug("PV forecast step")

            # Set unique ID based on location and solar configuration
            unique_id = f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}_{user_input[CONF_KWP]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return await self.async_step_load_forecast()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=49.5962536): vol.Coerce(float),
                vol.Required(CONF_AZIMUTH, default=124): vol.Coerce(int),
                vol.Required(CONF_LONGITUDE, default=18.3395664): vol.Coerce(float),
                vol.Required(CONF_KWP, default=6.44): vol.Coerce(float),
                vol.Required(CONF_DECLINATION, default=40): vol.Coerce(int),
                vol.Optional(CONF_API_KEY): str,
                vol.Optional(CONF_PV_FORECAST_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="pv_forecast",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_load_forecast(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Load forecast step: optional entity, else automatic profile."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            _LOGGER.debug("Load forecast step")

            return await self.async_step_inverter()

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_LOAD_FORECAST_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="load_forecast",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_inverter(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle inverter configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            _LOGGER.debug("Inverter data step")

            _LOGGER.info("Creating Photoptimizer entry with entities")
            return self.async_create_entry(title="Photoptimizer", data=self._data)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CURRENT_SOLAR_PRODUCTION_ENTITY
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
                vol.Required(CONF_CURRENT_CONSUMPTION_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
                vol.Required(CONF_GRID_POWER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
                vol.Required(CONF_BATTERY_SOC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        multiple=False,
                    )
                ),
                vol.Required(CONF_BATTERY_CAPACITY_KWH): vol.Coerce(float),
                vol.Required(
                    CONF_BATTERY_SOC_RESERVE_PERCENT,
                    default=DEFAULT_BATTERY_SOC_RESERVE_PERCENT,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_BATTERY_EFFICIENCY_ROUND_TRIP,
                    default=DEFAULT_BATTERY_EFFICIENCY_ROUND_TRIP,
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_WEAR_COST_PER_KWH, default=DEFAULT_WEAR_COST_PER_KWH
                ): vol.Coerce(float),
                vol.Required(CONF_EMHASS_URL, default=DEFAULT_EMHASS_URL): str,
                vol.Optional(CONF_EMHASS_TOKEN): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )

        return self.async_show_form(
            step_id="inverter",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of EMHASS connection settings."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_EMHASS_URL: user_input[CONF_EMHASS_URL],
                    CONF_EMHASS_TOKEN: user_input.get(CONF_EMHASS_TOKEN) or None,
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_EMHASS_URL): str,
                        vol.Optional(CONF_EMHASS_TOKEN): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        ),
                    }
                ),
                {
                    CONF_EMHASS_URL: entry.data.get(
                        CONF_EMHASS_URL,
                        DEFAULT_EMHASS_URL,
                    ),
                    CONF_EMHASS_TOKEN: entry.data.get(CONF_EMHASS_TOKEN),
                },
            ),
            errors={},
        )
