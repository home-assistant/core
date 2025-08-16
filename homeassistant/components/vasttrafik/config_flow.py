"""Config flow for Västtrafik integration."""

from __future__ import annotations

import logging
from typing import Any

import vasttrafik
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
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

async def search_stations(hass: HomeAssistant, config_entry, query: str) -> tuple[list[dict], str | None]:
    """Search for stations using the Västtrafik API.

    Returns (stations_list, error_code).
    """
    if not query or len(query) < 2:
        return [], None

    try:
        # Use the existing planner - it handles token refresh automatically
        planner = config_entry.runtime_data

        # Search for stations - the library handles token refresh automatically
        results = await hass.async_add_executor_job(planner.location_name, query)

        # Format results for dropdown
        stations = []
        for result in results[:10]:  # Limit to 10 results
            name = result.get("name", "")
            gid = result.get("gid", "")
            if name and gid:
                stations.append({
                    "value": name,
                    "label": f"{name} ({gid})"
                })

        if stations:
            return stations, None
        return [], "no_stations_found"

    except vasttrafik.Error as err:
        _LOGGER.error("Västtrafik API error in search_stations: %s", err)
        return [], "api_error"
    except Exception:
        _LOGGER.exception("Unexpected error in search_stations")
        return [], "api_error"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Create planner in the executor since constructor makes blocking HTTP calls
    planner = await hass.async_add_executor_job(
        vasttrafik.JournyPlanner, data[CONF_KEY], data[CONF_SECRET]
    )

    # Test the connection by making a simple API call
    try:
        await hass.async_add_executor_job(
            planner.location_name, "Centralstationen"
        )
    except vasttrafik.Error as err:
        _LOGGER.error("Failed to validate Västtrafik credentials: %s", err)
        if hasattr(err, 'response') and err.response and err.response.status_code in (401, 403):
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


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Check if we already have a main Västtrafik integration configured
        existing_entries = self._async_current_entries(include_ignore=False)
        main_entry = None
        for entry in existing_entries:
            if entry.data.get("is_departure_board") is not True:
                main_entry = entry
                break

        if main_entry:
            # Main integration exists, this will be a departure board
            return await self.async_step_departure_board()
        # No main integration, set up credentials first
        return await self.async_step_credentials()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials setup for main integration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Set unique ID for main integration
            await self.async_set_unique_id(f"{DOMAIN}_main")
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
                return self.async_create_entry(
                    title="Västtrafik",
                    data={**user_input, "is_departure_board": False}
                )

        return self.async_show_form(
            step_id="credentials", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_departure_board(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a departure board."""
        if user_input is not None:
            search_query = user_input.get("search_query", "").strip()
            if not search_query:
                errors = {"base": "search_required"}
            elif len(search_query) < 2:
                errors = {"base": "search_too_short"}
            else:
                # Get main entry for API access
                main_entry = self._get_main_entry()
                if not main_entry:
                    return self.async_abort(reason="no_main_integration")

                # Search for stations
                stations, error_code = await search_stations(self.hass, main_entry, search_query)
                if error_code:
                    errors = {"base": error_code}
                elif not stations:
                    errors = {"base": "no_stations_found"}
                else:
                    # Store search results and proceed to station selection
                    self._search_results = stations
                    return await self.async_step_select_departure_station()
        else:
            errors = {}

        search_schema = vol.Schema({
            vol.Required("search_query"): vol.All(str, vol.Length(min=2)),
        })

        return self.async_show_form(
            step_id="departure_board",
            data_schema=search_schema,
            errors=errors,
        )

    def _get_main_entry(self):
        """Get the main Västtrafik integration entry."""
        existing_entries = self._async_current_entries(include_ignore=False)
        for entry in existing_entries:
            if entry.data.get("is_departure_board") is not True:
                return entry
        return None

    async def async_step_select_departure_station(self, user_input=None):
        """Select station and configure departure sensor."""
        errors = {}

        if user_input is not None:
            selected_station = user_input.get("station")
            if not selected_station:
                errors["base"] = "station_required"
            else:
                self._selected_station = selected_station
                return await self.async_step_configure_departure_sensor()

        station_options = {station["value"]: station["label"] for station in self._search_results}

        station_schema = vol.Schema({
            vol.Required("station"): vol.In(station_options),
        })

        return self.async_show_form(
            step_id="select_departure_station",
            data_schema=station_schema,
            errors=errors,
        )

    async def async_step_configure_departure_sensor(self, user_input=None):
        """Configure the departure sensor details."""
        errors = {}

        if user_input is not None:
            lines = []
            if user_input.get(CONF_LINES):
                lines = [line.strip() for line in user_input[CONF_LINES].split(",") if line.strip()]

            tracks = []
            if user_input.get(CONF_TRACKS):
                tracks = [track.strip() for track in user_input[CONF_TRACKS].split(",") if track.strip()]

            station_name = self._selected_station
            unique_id = f"{DOMAIN}_departure_{station_name.lower().replace(' ', '_')}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_NAME: user_input.get(CONF_NAME, station_name)}
            )

            departure_data = {
                CONF_FROM: station_name,
                CONF_NAME: user_input.get(CONF_NAME, station_name),
                CONF_HEADING: user_input.get(CONF_HEADING, ""),  # Keep for backward compatibility
                CONF_LINES: lines,
                CONF_TRACKS: tracks,
                CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
                "is_departure_board": True,
            }

            return self.async_create_entry(
                title=f"Departure: {departure_data[CONF_NAME]}",
                data=departure_data
            )

        configure_schema = vol.Schema({
            vol.Optional(CONF_NAME): str,
            vol.Optional(CONF_HEADING): str,
            vol.Optional(CONF_LINES): str,
            vol.Optional(CONF_TRACKS): str,
            vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): vol.Coerce(int),
        })

        return self.async_show_form(
            step_id="configure_departure_sensor",
            data_schema=configure_schema,
            errors=errors,
            description_placeholders={
                "station_name": self._selected_station,
                "lines_help": "Enter line numbers separated by commas (e.g. 1, 2, 55)",
                "tracks_help": "Enter track/platform numbers separated by commas (e.g. A, B, 1, 2)"
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class VasttrafikOptionsFlow(OptionsFlow):
    """Handle options flow for Västtrafik departure boards."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        # Only departure boards can be reconfigured
        if not self.config_entry.data.get("is_departure_board"):
            return self.async_abort(reason="not_configurable")

        if user_input is not None:
            # Process lines input (convert comma-separated string to list)
            lines = []
            if user_input.get(CONF_LINES):
                lines = [line.strip() for line in user_input[CONF_LINES].split(",") if line.strip()]

            # Process tracks input (convert comma-separated string to list)
            tracks = []
            if user_input.get(CONF_TRACKS):
                tracks = [track.strip() for track in user_input[CONF_TRACKS].split(",") if track.strip()]

            # Update config entry data with new settings
            new_data = self.config_entry.data.copy()
            new_data.update({
                CONF_NAME: user_input.get(CONF_NAME, new_data.get(CONF_NAME)),
                CONF_HEADING: user_input.get(CONF_HEADING, ""),
                CONF_LINES: lines,
                CONF_TRACKS: tracks,
                CONF_DELAY: user_input.get(CONF_DELAY, new_data.get(CONF_DELAY, DEFAULT_DELAY)),
            })

            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                title=f"Departure: {new_data[CONF_NAME]}"
            )

            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Get current settings
        current_data = self.config_entry.data
        current_lines = current_data.get(CONF_LINES, [])
        current_tracks = current_data.get(CONF_TRACKS, [])

        # Convert lists back to comma-separated strings for the form
        lines_str = ", ".join(current_lines) if current_lines else ""
        tracks_str = ", ".join(current_tracks) if current_tracks else ""

        configure_schema = vol.Schema({
            vol.Optional(CONF_NAME, default=current_data.get(CONF_NAME, "")): str,
            vol.Optional(CONF_HEADING, default=current_data.get(CONF_HEADING, "")): str,
            vol.Optional(CONF_LINES, default=lines_str): str,
            vol.Optional(CONF_TRACKS, default=tracks_str): str,
            vol.Optional(CONF_DELAY, default=current_data.get(CONF_DELAY, DEFAULT_DELAY)): vol.Coerce(int),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=configure_schema,
            description_placeholders={
                "station_name": current_data.get(CONF_FROM, "Unknown"),
            }
        )
