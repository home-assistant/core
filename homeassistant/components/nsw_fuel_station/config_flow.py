"""Adds config flow for NSW Fuel Check."""

from __future__ import annotations

import logging
from typing import Any

import nsw_fuel
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SCAN_INTERVAL, StationPriceData, fetch_station_price_data
from .const import (
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
    DOMAIN,
    INPUT_FUEL_TYPES,
    INPUT_SEARCH_TERM,
    INPUT_STATION_ID,
)

_LOGGER = logging.getLogger(__name__)


class FuelCheckConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuel Check integration."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    config_type: str | None
    fuel_types: list[str]
    stations: list[nsw_fuel.Station]
    selected_station: nsw_fuel.Station
    data: StationPriceData

    async def _setup_coordinator(self):
        client = nsw_fuel.FuelCheckClient()

        async def async_update_data():
            return await self.hass.async_add_executor_job(
                fetch_station_price_data, client
            )

        coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            config_entry=None,
            name="sensor",
            update_interval=SCAN_INTERVAL,
            update_method=async_update_data,
        )
        self.hass.data[DOMAIN] = coordinator

        await coordinator.async_refresh()
        self.data = coordinator.data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display the initial UI form."""
        errors: dict[str, str] = {}

        await self._setup_coordinator()
        if self.data is None:
            return self.async_abort(reason="fetch_failed")

        if user_input is not None:
            search_term = user_input[INPUT_SEARCH_TERM]
            self.stations = [
                station
                for station in self.data.stations.values()
                if (
                    search_term.lower() in station.name.lower()
                    or search_term.lower() in station.address.lower()
                )
            ]
            if not self.stations:
                errors["base"] = "no_matching_stations"
            else:
                return await self.async_step_select_station()

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(INPUT_SEARCH_TERM): str,
                },
            ),
        )

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the station selector form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = int(user_input[INPUT_STATION_ID])
            self.selected_station = next(
                station for station in self.stations if station.code == station_id
            )
            await self.async_set_unique_id(str(station_id))
            self._abort_if_unique_id_configured()
            if "base" not in errors:
                return await self.async_step_select_fuel()

        return self.async_show_form(
            step_id="select_station",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(INPUT_STATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=str(station.code),
                                    label=f"{station.name} - {station.address}",
                                )
                                for station in self.stations
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                },
            ),
        )

    async def async_step_select_fuel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the fuel type selection form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=self.selected_station.name,
                data={
                    CONF_STATION_ID: self.selected_station.code,
                    CONF_FUEL_TYPES: user_input[INPUT_FUEL_TYPES],
                },
            )

        valid_fuel_types = {
            fuel_type: self.data.fuel_types.get(fuel_type, fuel_type)
            for station_code, fuel_type in self.data.prices
            if station_code == self.selected_station.code
        }

        if len(valid_fuel_types) < 1:
            return self.async_abort(reason="no_fuel_types")

        return self.async_show_form(
            step_id="select_fuel",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(INPUT_FUEL_TYPES): cv.multi_select(valid_fuel_types),
                }
            ),
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import entries from yaml config."""
        if not user_input:
            return self.async_abort(reason="no_config")
        station_id = user_input[INPUT_STATION_ID]
        data = {
            CONF_STATION_ID: station_id,
            CONF_FUEL_TYPES: user_input[INPUT_FUEL_TYPES],
        }
        await self.async_set_unique_id(str(station_id))
        self._abort_if_unique_id_configured()

        await self._setup_coordinator()
        if self.data is None:
            return self.async_abort(reason="fetch_failed")

        station = self.data.stations.get(station_id)
        if station is None:
            return self.async_abort(reason="no_matching_stations")

        return self.async_create_entry(
            title=station.name,
            data=data,
        )
