"""Config flow for NMBS integration."""

from typing import Any, override

import probatio
from pyrail import IRail, PyRailError
from pyrail.models import StationDetails

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.helpers import entity_registry as er
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
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONNECTION_UNIQUE_ID_PREFIX,
    DOMAIN,
    LIVEBOARD_UNIQUE_ID_PREFIX,
)


class NMBSConfigFlow(ConfigFlow, domain=DOMAIN):
    """NMBS config flow."""

    def __init__(self) -> None:
        """Initialize."""
        self.stations: list[StationDetails] = []

    async def _fetch_stations(self) -> list[StationDetails]:
        """Fetch the stations."""
        api_client = IRail(session=async_get_clientsession(self.hass))
        try:
            stations_response = await api_client.get_stations()
        except (PyRailError, TimeoutError, ValueError, LookupError) as err:
            raise CannotConnect from err
        if stations_response is None:
            raise CannotConnect
        return stations_response.stations

    async def _fetch_stations_choices(self) -> list[SelectOptionDict]:
        """Fetch the stations options."""

        if len(self.stations) == 0:
            self.stations = await self._fetch_stations()

        return [
            SelectOptionDict(value=station.id, label=station.standard_name)
            for station in self.stations
        ]

    def _route(
        self, user_input: dict[str, Any]
    ) -> tuple[StationDetails, StationDetails, str]:
        """Return the stations and the unique ID of the submitted route."""
        stations = {station.id: station for station in self.stations}
        station_from = stations[user_input[CONF_STATION_FROM]]
        station_to = stations[user_input[CONF_STATION_TO]]
        vias = "_excl_vias" if user_input.get(CONF_EXCLUDE_VIAS) else ""
        return station_from, station_to, f"{station_from.id}_{station_to.id}{vias}"

    def _async_migrate_entities(
        self,
        entry: ConfigEntry,
        unique_id: str,
        station_from: StationDetails,
        station_to: StationDetails,
    ) -> None:
        """Migrate the entities of the entry to the unique IDs of the new route.

        Entity unique IDs embed the route, so they change with it.
        """
        unique_ids = {
            f"{CONNECTION_UNIQUE_ID_PREFIX}{entry.unique_id}": (
                f"{CONNECTION_UNIQUE_ID_PREFIX}{unique_id}"
            ),
            f"{LIVEBOARD_UNIQUE_ID_PREFIX}{entry.data[CONF_STATION_FROM]}_{entry.unique_id}": (
                f"{LIVEBOARD_UNIQUE_ID_PREFIX}{station_from.id}_{unique_id}"
            ),
            f"{LIVEBOARD_UNIQUE_ID_PREFIX}{entry.data[CONF_STATION_TO]}_{entry.unique_id}": (
                f"{LIVEBOARD_UNIQUE_ID_PREFIX}{station_to.id}_{unique_id}"
            ),
        }
        entity_registry = er.async_get(self.hass)
        for old_unique_id, new_unique_id in unique_ids.items():
            entity_id = entity_registry.async_get_entity_id(
                "sensor", DOMAIN, old_unique_id
            )
            if entity_id is None:
                continue
            if not entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id):
                entity_registry.async_update_entity(
                    entity_id, new_unique_id=new_unique_id
                )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to setup a connection between 2 stations."""

        try:
            choices = await self._fetch_stations_choices()
        except CannotConnect:
            return self.async_abort(reason="api_unavailable")

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_STATION_FROM] == user_input[CONF_STATION_TO]:
                errors["base"] = "same_station"
            else:
                station_from, station_to, unique_id = self._route(user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_route_title(station_from, station_to),
                    data=user_input,
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_STATION_FROM): SelectSelector(
                    SelectSelectorConfig(
                        options=choices,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(CONF_STATION_TO): SelectSelector(
                    SelectSelectorConfig(
                        options=choices,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Optional(CONF_EXCLUDE_VIAS): BooleanSelector(),
                probatio.Optional(CONF_SHOW_ON_MAP): BooleanSelector(),
            },
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the monitored route."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        try:
            choices = await self._fetch_stations_choices()
        except CannotConnect:
            return self.async_abort(reason="api_unavailable")

        if user_input is not None:
            if user_input[CONF_STATION_FROM] == user_input[CONF_STATION_TO]:
                errors["base"] = "same_station"
            else:
                station_from, station_to, unique_id = self._route(user_input)
                if unique_id != entry.unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    self._async_migrate_entities(
                        entry, unique_id, station_from, station_to
                    )
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=_route_title(station_from, station_to),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_STATION_FROM, default=entry.data[CONF_STATION_FROM]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=choices,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Required(
                        CONF_STATION_TO, default=entry.data[CONF_STATION_TO]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=choices,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Optional(
                        CONF_EXCLUDE_VIAS,
                        default=entry.data.get(CONF_EXCLUDE_VIAS, False),
                    ): BooleanSelector(),
                    probatio.Optional(
                        CONF_SHOW_ON_MAP,
                        default=entry.data.get(CONF_SHOW_ON_MAP, False),
                    ): BooleanSelector(),
                }
            ),
            errors=errors,
        )


def _route_title(station_from: StationDetails, station_to: StationDetails) -> str:
    """Return the config entry title of a route."""
    return f"Train from {station_from.standard_name} to {station_to.standard_name}"


class CannotConnect(Exception):
    """Error to indicate we cannot connect to NMBS."""
