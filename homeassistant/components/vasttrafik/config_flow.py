"""Config flow for Västtrafik integration."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import vasttrafik
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DEPARTURES,
    CONF_FROM,
    CONF_HEADING,
    CONF_KEY,
    CONF_LINES,
    CONF_SEARCH_QUERY,
    CONF_SECRET,
    CONF_STATION_GID,
    CONF_STATION_NAME,
    CONF_TRACKS,
    DEFAULT_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY): TextSelector(),
        vol.Required(CONF_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

CONFIGURE_DEPARTURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Optional(CONF_HEADING): TextSelector(),
        vol.Optional(CONF_LINES): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Optional(CONF_TRACKS): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): NumberSelector(
            NumberSelectorConfig(unit_of_measurement="min")
        ),
    }
)


class StationData(TypedDict):
    """Station data from the Västtrafik API."""

    gid: str
    name: str


async def search_stations(
    hass: HomeAssistant, config_entry: ConfigEntry, query: str
) -> tuple[list[StationData], str | None]:
    """Search for stations using the Västtrafik API.

    Returns (stations_list, error_code).
    """
    if not query or len(query) < 2:
        return [], None

    planner = config_entry.runtime_data
    try:
        api_result: list[dict[str, str]] = await hass.async_add_executor_job(
            planner.location_name, query
        )
        results = [
            StationData(gid=result["gid"], name=result["name"]) for result in api_result
        ]
    except vasttrafik.Error as err:
        _LOGGER.error("Västtrafik API error in search_stations: %s", err)
        return [], "api_error"
    except Exception:
        _LOGGER.exception("Unexpected error in search_stations")
        return [], "api_error"

    if results:
        return results, None
    return [], "no_stations_found"


async def validate_api_credentials(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate that the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.

    Returns errors if any
    """

    try:
        planner = await hass.async_add_executor_job(
            vasttrafik.JournyPlanner, data[CONF_KEY], data[CONF_SECRET]
        )
        await hass.async_add_executor_job(planner.location_name, "Centralstationen")
    except vasttrafik.Error as err:
        _LOGGER.error("Failed to validate Västtrafik credentials: %s", err)
        if (
            hasattr(err, "response")
            and err.response
            and err.response.status_code in (401, 403)
        ):
            return {"base": "invalid_auth"}
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected error validating Västtrafik credentials")
        return {"base": "unknown"}

    return {}


class VasttrafikConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Västtrafik."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Get supported subentry types."""
        return {"departure_board": VasttrafikSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_KEY: user_input[CONF_KEY], CONF_SECRET: user_input[CONF_SECRET]}
            )
            if not (errors := await validate_api_credentials(self.hass, user_input)):
                return self.async_create_entry(title="Västtrafik", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of API credentials."""
        entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_KEY: user_input[CONF_KEY], CONF_SECRET: user_input[CONF_SECRET]}
            )
            if not (errors := await validate_api_credentials(self.hass, user_input)):
                return self.async_update_and_abort(
                    entry,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    def get_station_data(
        self, planner: vasttrafik.JournyPlanner, location: str
    ) -> StationData:
        """Get the station ID from either station name or station ID.

        This is used during the import process only.
        """
        if location.isdecimal():
            station_data = StationData(
                name=location, gid=location
            )  # no good way to get name from GID
        else:
            api_result: dict[str, str] = planner.location_name(location)[0]
            station_data = StationData(name=api_result["name"], gid=api_result["gid"])
        return station_data

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        self._async_abort_entries_match(
            {CONF_KEY: import_data[CONF_KEY], CONF_SECRET: import_data[CONF_SECRET]}
        )

        if errors := await validate_api_credentials(self.hass, import_data):
            return self.async_abort(reason=errors["base"])

        try:
            planner: vasttrafik.JournyPlanner = await self.hass.async_add_executor_job(
                vasttrafik.JournyPlanner,
                import_data[CONF_KEY],
                import_data[CONF_SECRET],
            )
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="unknown")

        subentries = []
        for departure in import_data.get(CONF_DEPARTURES, []):
            try:
                station_data = await self.hass.async_add_executor_job(
                    self.get_station_data, planner, departure[CONF_FROM]
                )
            except Exception:  # noqa: BLE001
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "deprecated_yaml_import_issue_station_not_found",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="deprecated_yaml_import_issue_station_not_found",
                    translation_placeholders={"station": departure[CONF_FROM]},
                )
                continue

            subentries.append(
                ConfigSubentryData(
                    title=departure.get(CONF_NAME, station_data["name"]),
                    subentry_type="departure_board",
                    data={
                        CONF_STATION_GID: station_data["gid"],
                        CONF_NAME: departure.get(CONF_NAME, station_data["name"]),
                        CONF_HEADING: departure.get(CONF_HEADING),
                        CONF_LINES: departure.get(CONF_LINES, []),
                        CONF_TRACKS: departure.get(CONF_TRACKS, []),
                        CONF_DELAY: departure.get(CONF_DELAY, DEFAULT_DELAY),
                    },
                    unique_id=None,
                )
            )

        create_entry_result = self.async_create_entry(
            title="Västtrafik",
            data={
                CONF_KEY: import_data[CONF_KEY],
                CONF_SECRET: import_data[CONF_SECRET],
            },
            subentries=subentries,
        )

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_yaml_import_success",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_success",
        )

        return create_entry_result


class VasttrafikSubentryFlow(ConfigSubentryFlow):
    """Handle a subentry config flow for Västtrafik departure boards."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self._search_results: list[StationData] = []
        self._selected_station: StationData | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step of adding a departure board."""
        if user_input is not None:
            search_query = user_input[CONF_SEARCH_QUERY].strip()
            if not search_query:
                errors = {"base": "search_required"}
            else:
                parent_entry = self._get_entry()

                stations, error_code = await search_stations(
                    self.hass, parent_entry, search_query
                )
                if error_code:
                    errors = {"base": error_code}
                elif not stations:
                    errors = {"base": "no_stations_found"}
                else:
                    self._search_results = stations
                    return await self.async_step_select_station()
        else:
            errors = {}

        search_schema = vol.Schema(
            {
                vol.Required(CONF_SEARCH_QUERY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.SEARCH)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=search_schema,
            errors=errors,
        )

    async def async_step_select_station(
        self, user_input: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Select station and configure departure sensor."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_station = [
                v for v in self._search_results if v["gid"] == user_input["station"]
            ][0]
            return await self.async_step_configure()

        selector_options = [
            SelectOptionDict(value=v["gid"], label=v["name"])
            for v in self._search_results
        ]

        station_schema = vol.Schema(
            {
                vol.Required("station"): SelectSelector(
                    SelectSelectorConfig(options=selector_options)
                ),
            }
        )

        return self.async_show_form(
            step_id="select_station",
            data_schema=station_schema,
            errors=errors,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure the departure sensor details."""
        assert self._selected_station is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            departure_data = {
                CONF_STATION_GID: self._selected_station["gid"],
                CONF_STATION_NAME: self._selected_station["name"],
                CONF_NAME: user_input.get(CONF_NAME),
                CONF_HEADING: user_input.get(CONF_HEADING, ""),
                CONF_LINES: user_input.get(CONF_LINES, []),
                CONF_TRACKS: user_input.get(CONF_TRACKS, []),
                CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
            }

            return self.async_create_entry(
                title=f"Departure: {departure_data[CONF_NAME]}",
                data=departure_data,
            )

        return self.async_show_form(
            step_id="configure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIGURE_DEPARTURE_SCHEMA,
                {
                    CONF_NAME: self._selected_station["name"],
                },
            ),
            errors=errors,
            description_placeholders={"station_name": self._selected_station["name"]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a departure board."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            new_data = {
                CONF_STATION_GID: subentry.data[CONF_STATION_GID],
                CONF_STATION_NAME: subentry.data[CONF_STATION_NAME],
                CONF_NAME: user_input.get(CONF_NAME, subentry.data[CONF_NAME]),
                CONF_HEADING: user_input.get(CONF_HEADING, ""),
                CONF_LINES: user_input.get(CONF_LINES, []),
                CONF_TRACKS: user_input.get(CONF_TRACKS, []),
                CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
            }

            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data=new_data,
                title=f"Departure: {new_data[CONF_NAME]}",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIGURE_DEPARTURE_SCHEMA, user_input or subentry.data
            ),
            description_placeholders={
                "station_name": subentry.data.get(CONF_STATION_NAME, "Unknown"),
            },
        )
