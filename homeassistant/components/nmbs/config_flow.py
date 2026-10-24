"""Config flow for NMBS integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pyrail.models import StationDetails

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
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
from .coordinator import StationListUnavailableError, async_fetch_stations


class NMBSConfigFlow(ConfigFlow, domain=DOMAIN):
    """NMBS config flow."""

    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self.stations: list[StationDetails] = []

    async def _fetch_stations_choices(self) -> list[SelectOptionDict]:
        """Fetch the stations options."""

        if len(self.stations) == 0:
            self.stations = await async_fetch_stations(self.hass)

        return [
            SelectOptionDict(value=station.id, label=station.standard_name)
            for station in self.stations
        ]

    def _route(
        self, user_input: dict[str, Any]
    ) -> tuple[StationDetails, StationDetails]:
        """Return the stations of the submitted route."""
        stations = {station.id: station for station in self.stations}
        return (
            stations[user_input[CONF_STATION_FROM]],
            stations[user_input[CONF_STATION_TO]],
        )

    def _async_migrate_entities(self, entry: ConfigEntry, unique_id: str) -> None:
        """Migrate the entities of the entry to its new unique ID.

        Entity unique IDs embed the entry unique ID, so they change with it.
        """
        unique_ids = {
            f"{CONNECTION_UNIQUE_ID_PREFIX}{entry.unique_id}": (
                f"{CONNECTION_UNIQUE_ID_PREFIX}{unique_id}"
            ),
        }
        for station_id in (entry.data[CONF_STATION_FROM], entry.data[CONF_STATION_TO]):
            prefix = f"{LIVEBOARD_UNIQUE_ID_PREFIX}{station_id}_"
            unique_ids[f"{prefix}{entry.unique_id}"] = f"{prefix}{unique_id}"
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
        except StationListUnavailableError:
            return self.async_abort(reason="api_unavailable")

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_STATION_FROM] == user_input[CONF_STATION_TO]:
                errors["base"] = "same_station"
            else:
                station_from, station_to = self._route(user_input)
                await self.async_set_unique_id(_route_unique_id(user_input))
                self._abort_if_unique_id_configured()
                data = dict(user_input)
                show_on_map = data.pop(CONF_SHOW_ON_MAP, False)
                return self.async_create_entry(
                    title=_route_title(station_from, station_to),
                    data=data,
                    options={CONF_SHOW_ON_MAP: show_on_map},
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

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> NMBSOptionsFlow:
        """Return the options flow."""
        return NMBSOptionsFlow()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the connection."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            unique_id = _route_unique_id({**entry.data, **user_input})
            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                self._async_migrate_entities(entry, unique_id)
            return self.async_update_reload_and_abort(
                entry,
                unique_id=unique_id,
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_EXCLUDE_VIAS,
                        default=entry.data.get(CONF_EXCLUDE_VIAS, False),
                    ): BooleanSelector(),
                }
            ),
        )


class NMBSOptionsFlow(OptionsFlowWithReload):
    """NMBS options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the display options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_SHOW_ON_MAP,
                        default=self.config_entry.options.get(CONF_SHOW_ON_MAP, False),
                    ): BooleanSelector(),
                }
            ),
        )


def _route_unique_id(data: Mapping[str, Any]) -> str:
    """Return the config entry unique ID of a route."""
    vias = "_excl_vias" if data.get(CONF_EXCLUDE_VIAS) else ""
    return f"{data[CONF_STATION_FROM]}_{data[CONF_STATION_TO]}{vias}"


def _route_title(station_from: StationDetails, station_to: StationDetails) -> str:
    """Return the config entry title of a route."""
    return f"Train from {station_from.standard_name} to {station_to.standard_name}"
