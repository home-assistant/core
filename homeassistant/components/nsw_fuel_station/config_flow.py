"""Adds config flow for NSW Fuel Check."""

from __future__ import annotations

import logging
from typing import Any

import nsw_fuel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import StationPriceData, fetch_station_price_data
from .const import CONF_STATION_ID, DOMAIN, INPUT_SEARCH_TERM, INPUT_STATION_ID

_LOGGER = logging.getLogger(__name__)


class NswFuelStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuel Check integration."""

    VERSION = 1

    config_type: str | None
    fuel_types: list[str]
    stations: list[nsw_fuel.Station]
    selected_station: nsw_fuel.Station
    data: StationPriceData | None

    async def _fetch_fuel_data(self) -> None:
        client = nsw_fuel.FuelCheckClient()
        self.data = None
        try:
            self.data = await self.hass.async_add_executor_job(
                fetch_station_price_data, client
            )
        except UpdateFailed as e:
            _LOGGER.error("Error fetching data from NSW Fuel API: %s", e)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display the initial UI form."""
        errors: dict[str, str] = {}

        await self._fetch_fuel_data()
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
                return self.async_create_entry(
                    title=self.selected_station.name,
                    data={
                        CONF_STATION_ID: self.selected_station.code,
                    },
                )

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

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import entries from yaml config."""
        if not user_input:
            return self.async_abort(reason="no_config")
        station_id = user_input[INPUT_STATION_ID]
        await self.async_set_unique_id(str(station_id))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Station {station_id}",
            data={
                CONF_STATION_ID: station_id,
            },
        )
