"""Config flow for NMBS integration."""

from typing import Any

from pyrail import iRail
from pyrail.models import StationDetails
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_EXCLUDE_VIAS,
    CONF_SHOW_ON_MAP,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)


class NMBSConfigFlow(ConfigFlow, domain=DOMAIN):
    """NMBS config flow."""

    def __init__(self) -> None:
        """Initialize."""
        self.stations: list[StationDetails] = []

    async def _fetch_stations(self) -> list[StationDetails]:
        """Fetch the stations."""
        api_client = iRail(session=async_get_clientsession(self.hass))
        stations_response = await api_client.get_stations()
        if stations_response is None:
            raise CannotConnect("The API is currently unavailable.")
        return stations_response.stations

    async def _fetch_stations_choices(self) -> list[SelectOptionDict]:
        """Fetch the stations options."""

        if len(self.stations) == 0:
            self.stations = await self._fetch_stations()

        return [
            SelectOptionDict(value=station.id, label=station.standard_name)
            for station in self.stations
        ]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to setup a connection between 2 stations."""

        try:
            choices = await self._fetch_stations_choices()
        except CannotConnect:
            return self.async_abort(reason="api_unavailable")

        errors: dict = {}
        if user_input is not None:
            if user_input[CONF_STATION_FROM] == user_input[CONF_STATION_TO]:
                errors["base"] = "same_station"
            else:
                [station_from] = [
                    station
                    for station in self.stations
                    if station.id == user_input[CONF_STATION_FROM]
                ]
                [station_to] = [
                    station
                    for station in self.stations
                    if station.id == user_input[CONF_STATION_TO]
                ]
                vias = "_excl_vias" if user_input.get(CONF_EXCLUDE_VIAS) else ""
                await self.async_set_unique_id(
                    f"{user_input[CONF_STATION_FROM]}_{user_input[CONF_STATION_TO]}{vias}"
                )
                self._abort_if_unique_id_configured()

                config_entry_name = f"Train from {station_from.standard_name} to {station_to.standard_name}"
                return self.async_create_entry(
                    title=config_entry_name,
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_FROM): SelectSelector(
                    SelectSelectorConfig(
                        options=choices,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_STATION_TO): SelectSelector(
                    SelectSelectorConfig(
                        options=choices,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_EXCLUDE_VIAS): BooleanSelector(),
                vol.Optional(CONF_SHOW_ON_MAP): BooleanSelector(),
            },
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect to NMBS."""
