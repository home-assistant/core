"""Config flow for the MVG integration."""

import hashlib
import json
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
    DEFAULT_TIMEOFFSET,
    DOMAIN,
)

ALL_PRODUCTS = [product.value[0] for product in TransportType.all()]

# Product names the legacy YAML accepted but mvg no longer knows.
LEGACY_PRODUCTS = {
    "ExpressBus": TransportType.BUS.value[0],
    "Nachteule": TransportType.BUS.value[0],
}
LEGACY_DEFAULT_PRODUCTS = ["U-Bahn", "Tram", "Bus", "ExpressBus", "S-Bahn", "Nachteule"]

# Filters that tell unnamed legacy entries for one station apart.
IMPORT_FILTER_KEYS = (
    CONF_DESTINATIONS,
    CONF_DIRECTIONS,
    CONF_LINES,
    CONF_PRODUCTS,
    CONF_TIMEOFFSET,
    CONF_NUMBER,
)

MAX_STATION_MATCHES = 25

PRODUCTS_SELECTOR = SelectSelector(
    SelectSelectorConfig(options=ALL_PRODUCTS, multiple=True)
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATION): str,
        vol.Optional(CONF_PRODUCTS, default=list): PRODUCTS_SELECTOR,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DESTINATIONS, default=DEFAULT_DESTINATIONS): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Optional(CONF_LINES, default=DEFAULT_LINES): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Optional(CONF_PRODUCTS, default=list): PRODUCTS_SELECTOR,
        vol.Optional(CONF_TIMEOFFSET, default=DEFAULT_TIMEOFFSET): cv.positive_int,
        vol.Optional(CONF_NUMBER, default=DEFAULT_NUMBER): cv.positive_int,
    }
)


def _filter_digest(import_data: dict[str, Any]) -> str:
    """Return a stable digest of the filters of one legacy YAML entry."""
    filters = {key: import_data.get(key) for key in IMPORT_FILTER_KEYS}
    payload = json.dumps(filters, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


def _migrate_products(products: list[str] | None) -> list[str]:
    """Map the product names of a legacy YAML entry onto transport types."""
    legacy = LEGACY_DEFAULT_PRODUCTS if products is None else products
    migrated = {LEGACY_PRODUCTS.get(product, product) for product in legacy}
    return [product for product in ALL_PRODUCTS if product in migrated]


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

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

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

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
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
            ),
        )

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

        # Legacy YAML allows several entries per station, so the optional
        # name or else the filter set has to keep them apart.
        name = import_data.get(CONF_NAME)
        suffix = name or _filter_digest(import_data)
        await self.async_set_unique_id(f"{station['id']}_{suffix}")
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
                CONF_PRODUCTS: _migrate_products(import_data.get(CONF_PRODUCTS)),
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
            return self.async_create_entry(
                data={
                    CONF_DESTINATIONS: user_input[CONF_DESTINATIONS]
                    or DEFAULT_DESTINATIONS,
                    CONF_LINES: user_input[CONF_LINES] or DEFAULT_LINES,
                    CONF_PRODUCTS: user_input[CONF_PRODUCTS],
                    CONF_TIMEOFFSET: user_input[CONF_TIMEOFFSET],
                    CONF_NUMBER: user_input[CONF_NUMBER],
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
