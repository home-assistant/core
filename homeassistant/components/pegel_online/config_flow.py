"""Config flow for PEGELONLINE."""
from __future__ import annotations

from typing import Any

from aiopegelonline import CONNECT_ERRORS, PegelOnline
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    UnitOfLength,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_STATION, DEFAULT_RADIUS, DOMAIN


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init the FlowHandler."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._stations: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self._show_form_user()

        api = PegelOnline(async_get_clientsession(self.hass))
        try:
            stations = await api.async_get_nearby_stations(
                user_input[CONF_LOCATION][CONF_LATITUDE],
                user_input[CONF_LOCATION][CONF_LONGITUDE],
                user_input[CONF_RADIUS],
            )
        except CONNECT_ERRORS:
            return self._show_form_user(user_input, errors={"base": "cannot_connect"})

        if len(stations) == 0:
            return self._show_form_user(user_input, errors={CONF_RADIUS: "no_stations"})

        for uuid, station in stations.items():
            self._stations[uuid] = f"{station.name} {station.water_name}"

        self._data = user_input

        return await self.async_step_select_station()

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step select_station of a flow initialized by the user."""
        if not user_input:
            stations = [
                SelectOptionDict(value=k, label=v) for k, v in self._stations.items()
            ]
            return self.async_show_form(
                step_id="select_station",
                description_placeholders={"stations_count": str(len(self._stations))},
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_STATION): SelectSelector(
                            SelectSelectorConfig(
                                options=stations, mode=SelectSelectorMode.DROPDOWN
                            )
                        )
                    }
                ),
            )

        await self.async_set_unique_id(user_input[CONF_STATION])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._stations[user_input[CONF_STATION]],
            data=user_input,
        )

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(
                            CONF_LOCATION,
                            {
                                "latitude": self.hass.config.latitude,
                                "longitude": self.hass.config.longitude,
                            },
                        ),
                    ): LocationSelector(),
                    vol.Required(
                        CONF_RADIUS, default=user_input.get(CONF_RADIUS, DEFAULT_RADIUS)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=100,
                            step=1,
                            unit_of_measurement=UnitOfLength.KILOMETERS,
                        ),
                    ),
                }
            ),
            errors=errors,
        )
