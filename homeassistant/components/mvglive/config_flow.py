"""Config flow for the MVG integration."""

from typing import Any, override

from mvg import MvgApi, MvgApiError, TransportType
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_DESTINATIONS,
    CONF_DIRECTIONS,
    CONF_LINES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_STATION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TIMEOFFSET,
    DEFAULT_DESTINATIONS,
    DEFAULT_LINES,
    DEFAULT_NUMBER,
    DEFAULT_PRODUCTS,
    DEFAULT_TIMEOFFSET,
    DOMAIN,
)

ALL_PRODUCTS = [product.value[0] for product in TransportType.all()]

MAX_STATION_MATCHES = 25


class MvgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MVG."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._matches: dict[str, dict[str, Any]] = {}
        self._products: list[str] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step: search for a station and pick modes of transport."""
        errors: dict[str, str] = {}
        if user_input is not None:
            search_term = user_input[CONF_STATION].strip().lower()
            try:
                all_stations = await MvgApi.stations_async()
            except MvgApiError:
                errors["base"] = "cannot_connect"
            else:
                matches = sorted(
                    (
                        station
                        for station in all_stations
                        if search_term in station["name"].lower()
                    ),
                    key=lambda station: station["name"],
                )[:MAX_STATION_MATCHES]
                if not matches:
                    errors["base"] = "invalid_station"
                else:
                    self._matches = {station["id"]: station for station in matches}
                    self._products = user_input[CONF_PRODUCTS]
                    return await self.async_step_select()

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION): str,
                vol.Optional(CONF_PRODUCTS, default=[]): SelectSelector(
                    SelectSelectorConfig(options=ALL_PRODUCTS, multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user pick the exact station from the search matches."""
        if user_input is not None:
            station = self._matches[user_input[CONF_STATION_ID]]
            await self.async_set_unique_id(station["id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=station["name"],
                data={
                    CONF_STATION_ID: station["id"],
                    CONF_STATION_NAME: station["name"],
                },
                options={CONF_PRODUCTS: self._products},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=station["id"],
                                label=f"{station['name']} ({station['place']})"
                                if station.get("place")
                                else station["name"],
                            )
                            for station in self._matches.values()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="select", data_schema=schema)

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import a single `nextdeparture` entry from YAML configuration."""
        try:
            station = await MvgApi.station_async(import_data[CONF_STATION])
        except MvgApiError:
            return self.async_abort(reason="cannot_connect")
        if station is None:
            return self.async_abort(reason="invalid_station")

        # `name` disambiguates multiple legacy entries for the same station.
        name = import_data.get(CONF_NAME)
        unique_id = f"{station['id']}_{name}" if name else station["id"]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # `directions` is a fallback: only used if `destinations` wasn't set.
        destinations = import_data.get(CONF_DESTINATIONS, DEFAULT_DESTINATIONS)
        if destinations == DEFAULT_DESTINATIONS and import_data.get(CONF_DIRECTIONS):
            destinations = import_data[CONF_DIRECTIONS]

        return self.async_create_entry(
            title=name or station["name"],
            data={
                CONF_STATION_ID: station["id"],
                CONF_STATION_NAME: station["name"],
            },
            options={
                CONF_DESTINATIONS: destinations,
                CONF_LINES: import_data.get(CONF_LINES, DEFAULT_LINES),
                CONF_PRODUCTS: import_data.get(CONF_PRODUCTS, DEFAULT_PRODUCTS),
                CONF_TIMEOFFSET: import_data.get(CONF_TIMEOFFSET, DEFAULT_TIMEOFFSET),
                CONF_NUMBER: import_data.get(CONF_NUMBER, DEFAULT_NUMBER),
            },
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MvgOptionsFlowHandler:
        """Create the options flow."""
        return MvgOptionsFlowHandler()


class MvgOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle MVG options: destinations, lines, products, timeoffset and number."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            options = {
                CONF_DESTINATIONS: user_input[CONF_DESTINATIONS] or [""],
                CONF_LINES: user_input[CONF_LINES] or [""],
                CONF_PRODUCTS: user_input[CONF_PRODUCTS],
                CONF_TIMEOFFSET: user_input[CONF_TIMEOFFSET],
                CONF_NUMBER: user_input[CONF_NUMBER],
            }
            return self.async_create_entry(data=options)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DESTINATIONS,
                    default=current.get(CONF_DESTINATIONS, DEFAULT_DESTINATIONS),
                ): TextSelector(TextSelectorConfig(multiple=True)),
                vol.Optional(
                    CONF_LINES,
                    default=current.get(CONF_LINES, DEFAULT_LINES),
                ): TextSelector(TextSelectorConfig(multiple=True)),
                vol.Optional(
                    CONF_PRODUCTS,
                    default=current.get(CONF_PRODUCTS) or [],
                ): SelectSelector(
                    SelectSelectorConfig(options=ALL_PRODUCTS, multiple=True)
                ),
                vol.Optional(
                    CONF_TIMEOFFSET,
                    default=current.get(CONF_TIMEOFFSET, DEFAULT_TIMEOFFSET),
                ): cv.positive_int,
                vol.Optional(
                    CONF_NUMBER,
                    default=current.get(CONF_NUMBER, DEFAULT_NUMBER),
                ): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
