"""Adds config flow for NSW Fuel Check."""

from __future__ import annotations

from typing import Any

from nsw_fuel import Station
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import StationPriceData
from .const import (
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
    DOMAIN,
    INPUT_FUEL_TYPES,
    INPUT_SEARCH_TERM,
    INPUT_STATION_ID,
)
from .coordinator import NswFuelStationDataUpdateCoordinator


class FuelCheckConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuel Check integration."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    config_type: str | None
    fuel_types: list[str]
    stations: list[Station]
    selected_station: Station
    data: StationPriceData

    async def _setup_coordinator(self):
        coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            coordinator = NswFuelStationDataUpdateCoordinator(self.hass)
            await coordinator.async_config_entry_first_refresh()
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
            for existing_entry in self._async_current_entries():
                if existing_entry.data[CONF_STATION_ID] == station_id:
                    errors["base"] = "station_exists"
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
            if (
                INPUT_FUEL_TYPES not in user_input
                or len(user_input[INPUT_FUEL_TYPES]) < 1
            ):
                errors["base"] = "missing_fuel_types"
            else:
                return self.async_create_entry(
                    title=self.selected_station.name,
                    data={
                        CONF_STATION_ID: self.selected_station.code,
                        CONF_FUEL_TYPES: user_input[INPUT_FUEL_TYPES],
                    },
                )

        valid_fuel_types = []
        for station_code, fuel_type in self.data.prices:
            if station_code == self.selected_station.code:
                valid_fuel_types.append(
                    SelectOptionDict(
                        label=self.data.fuel_types.get(fuel_type, fuel_type),
                        value=fuel_type,
                    )
                )

        if len(valid_fuel_types) < 1:
            return self.async_abort(reason="no_fuel_types")

        return self.async_show_form(
            step_id="select_fuel",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(INPUT_FUEL_TYPES): SelectSelector(
                        SelectSelectorConfig(
                            options=valid_fuel_types,
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
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
        self._async_abort_entries_match({CONF_STATION_ID: station_id})

        await self._setup_coordinator()
        if self.data is None:
            return self.async_abort(reason="fetch_failed")

        station = self.data.stations.get(station_id)
        name = "Unknown"
        if station is not None:
            name = station.name

        return self.async_create_entry(
            title=name,
            data=data,
        )
