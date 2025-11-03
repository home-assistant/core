"""Config flow for Västtrafik integration."""

from __future__ import annotations

import logging
from typing import Any

import vasttrafik
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_DEPARTURES,
    CONF_FROM,
    CONF_HEADING,
    CONF_KEY,
    CONF_LINES,
    CONF_SECRET,
    CONF_TRACKS,
    DEFAULT_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY): str,
        vol.Required(CONF_SECRET): str,
    }
)


async def search_stations(
    hass: HomeAssistant, config_entry: ConfigEntry, query: str
) -> tuple[list[dict[str, str]], str | None]:
    """Search for stations using the Västtrafik API.

    Returns (stations_list, error_code).
    """
    if not query or len(query) < 2:
        return [], None

    planner = config_entry.runtime_data
    try:
        results = await hass.async_add_executor_job(planner.location_name, query)
    except vasttrafik.Error as err:
        _LOGGER.error("Västtrafik API error in search_stations: %s", err)
        return [], "api_error"
    except Exception:
        _LOGGER.exception("Unexpected error in search_stations")
        return [], "api_error"

    stations = []
    for result in results[:10]:  # Limit to 10 results
        name = result.get("name", "")
        gid = result.get("gid", "")
        if name and gid:
            stations.append({"value": name, "label": f"{name} ({gid})"})

    if stations:
        return stations, None
    return [], "no_stations_found"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    planner = await hass.async_add_executor_job(
        vasttrafik.JournyPlanner, data[CONF_KEY], data[CONF_SECRET]
    )

    try:
        await hass.async_add_executor_job(planner.location_name, "Centralstationen")
    except vasttrafik.Error as err:
        _LOGGER.error("Failed to validate Västtrafik credentials: %s", err)
        if (
            hasattr(err, "response")
            and err.response
            and err.response.status_code in (401, 403)
        ):
            raise InvalidAuth from err
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.error("Unexpected error validating Västtrafik credentials: %s", err)
        raise CannotConnect from err

    return {"title": "Västtrafik"}


class VasttrafikConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Västtrafik."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return VasttrafikOptionsFlow()

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

        existing_entries = self._async_current_entries(include_ignore=False)
        if existing_entries:
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
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
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=user_input,
                    reload_even_if_entry_is_unchanged=False,
                )

        suggested_values = user_input or {
            CONF_KEY: entry.data[CONF_KEY],
            CONF_SECRET: entry.data[CONF_SECRET],
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        self._async_abort_entries_match(
            {CONF_KEY: import_data[CONF_KEY], CONF_SECRET: import_data[CONF_SECRET]}
        )

        try:
            await validate_input(self.hass, import_data)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            _LOGGER.exception("Unexpected exception during YAML import")
            return self.async_abort(reason="unknown")

        subentries: list[ConfigSubentryData] = []
        for departure in import_data.get(CONF_DEPARTURES, []):
            subentries.append(
                ConfigSubentryData(
                    title=departure.get(CONF_NAME, departure[CONF_FROM]),
                    subentry_type="departure_board",
                    data={
                        CONF_FROM: departure[CONF_FROM],
                        CONF_NAME: departure.get(CONF_NAME, departure[CONF_FROM]),
                        CONF_HEADING: departure.get(CONF_HEADING, ""),
                        CONF_LINES: departure.get(CONF_LINES, []),
                        CONF_TRACKS: departure.get(CONF_TRACKS, []),
                        CONF_DELAY: departure.get(CONF_DELAY, DEFAULT_DELAY),
                    },
                    unique_id=None,
                )
            )

        return self.async_create_entry(
            title="Västtrafik",
            data={CONF_KEY: import_data[CONF_KEY], CONF_SECRET: import_data[CONF_SECRET]},
            subentries=subentries,
        )


class VasttrafikSubentryFlow(ConfigSubentryFlow):
    """Handle a subentry config flow for Västtrafik departure boards."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self._search_results: list[dict] = []
        self._selected_station: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of adding a departure board."""
        if user_input is not None:
            search_query = user_input.get("search_query", "").strip()
            if not search_query:
                errors = {"base": "search_required"}
            elif len(search_query) < 2:
                errors = {"base": "search_too_short"}
            else:
                parent_entry = self._get_entry()
                if not parent_entry:
                    return self.async_abort(reason="parent_entry_not_found")

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
                vol.Required("search_query"): vol.All(str, vol.Length(min=2)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=search_schema,
            errors=errors,
        )

    async def async_step_select_station(self, user_input: dict[str, str] | None = None):
        """Select station and configure departure sensor."""
        errors = {}

        if user_input is not None:
            self._selected_station = user_input["station"]
            return await self.async_step_configure()

        station_options = {
            station["value"]: station["label"] for station in self._search_results
        }

        station_schema = vol.Schema(
            {
                vol.Required("station"): vol.In(station_options),
            }
        )

        return self.async_show_form(
            step_id="select_station",
            data_schema=station_schema,
            errors=errors,
        )

    async def async_step_configure(self, user_input=None):
        """Configure the departure sensor details."""
        errors = {}

        if user_input is not None:
            lines = []
            if user_input.get(CONF_LINES):
                lines = [
                    line.strip()
                    for line in user_input[CONF_LINES].split(",")
                    if line.strip()
                ]

            tracks = []
            if user_input.get(CONF_TRACKS):
                tracks = [
                    track.strip()
                    for track in user_input[CONF_TRACKS].split(",")
                    if track.strip()
                ]

            station_name = self._selected_station
            unique_id = f"departure_{station_name.lower().replace(' ', '_')}"

            departure_data = {
                CONF_FROM: station_name,
                CONF_NAME: user_input.get(CONF_NAME, station_name),
                CONF_HEADING: user_input.get(
                    CONF_HEADING, ""
                ),  # Keep for backward compatibility
                CONF_LINES: lines,
                CONF_TRACKS: tracks,
                CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
            }

            return self.async_create_entry(
                title=f"Departure: {departure_data[CONF_NAME]}",
                data=departure_data,
                unique_id=unique_id,
            )

        configure_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Optional(CONF_HEADING): str,
                vol.Optional(CONF_LINES): str,
                vol.Optional(CONF_TRACKS): str,
                vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): vol.Coerce(int),
            }
        )

        return self.async_show_form(
            step_id="configure",
            data_schema=configure_schema,
            errors=errors,
            description_placeholders={
                "station_name": self._selected_station,
                "lines_help": "Enter line numbers separated by commas (e.g. 1, 2, 55)",
                "tracks_help": "Enter track/platform numbers separated by commas (e.g. A, B, 1, 2)",
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of a departure board."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            lines = []
            if user_input.get(CONF_LINES):
                lines = [
                    line.strip()
                    for line in user_input[CONF_LINES].split(",")
                    if line.strip()
                ]

            tracks = []
            if user_input.get(CONF_TRACKS):
                tracks = [
                    track.strip()
                    for track in user_input[CONF_TRACKS].split(",")
                    if track.strip()
                ]

            new_data = {
                CONF_FROM: subentry.data[CONF_FROM],  # Keep original station
                CONF_NAME: user_input.get(CONF_NAME, subentry.data[CONF_NAME]),
                CONF_HEADING: user_input.get(CONF_HEADING, ""),
                CONF_LINES: lines,
                CONF_TRACKS: tracks,
                CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
            }

            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data=new_data,
                title=f"Departure: {new_data[CONF_NAME]}",
            )

        current_data = subentry.data
        current_lines = current_data.get(CONF_LINES, [])
        current_tracks = current_data.get(CONF_TRACKS, [])

        lines_str = ", ".join(current_lines) if current_lines else ""
        tracks_str = ", ".join(current_tracks) if current_tracks else ""

        configure_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=current_data.get(CONF_NAME, "")): str,
                vol.Optional(
                    CONF_HEADING, default=current_data.get(CONF_HEADING, "")
                ): str,
                vol.Optional(CONF_LINES, default=lines_str): str,
                vol.Optional(CONF_TRACKS, default=tracks_str): str,
                vol.Optional(
                    CONF_DELAY, default=current_data.get(CONF_DELAY, DEFAULT_DELAY)
                ): vol.Coerce(int),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=configure_schema,
            description_placeholders={
                "station_name": current_data.get(CONF_FROM, "Unknown"),
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class VasttrafikOptionsFlow(OptionsFlow):
    """Handle options flow for Västtrafik main integration."""

    async def async_step_init(self, user_input=None):
        """Manage the options for the main integration."""
        return self.async_abort(reason="not_configurable")
