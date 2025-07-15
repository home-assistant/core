"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import logging
from typing import Any, cast

from ns_api import NSAPI
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import CONF_FROM, CONF_NAME, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            # Only log API key validation attempt
            _LOGGER.debug("Validating user API key for NS integration")
            client = NSAPI(api_key)
            try:
                await self.hass.async_add_executor_job(client.get_stations)
            except ValueError as ex:
                _LOGGER.debug("API validation failed with ValueError: %s", ex)
                if (
                    "401" in str(ex)
                    or "unauthorized" in str(ex).lower()
                    or "invalid" in str(ex).lower()
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (ConnectionError, TimeoutError) as ex:
                _LOGGER.debug("API validation failed with connection error: %s", ex)
                errors["base"] = "cannot_connect"
            except (
                Exception  # Allowed in config flows for robustness  # noqa: BLE001
            ) as ex:
                _LOGGER.debug("API validation failed with unexpected error: %s", ex)
                if (
                    "401" in str(ex)
                    or "unauthorized" in str(ex).lower()
                    or "invalid" in str(ex).lower()
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            if not errors:
                # Use a stable unique ID instead of the API key since keys can be rotated
                await self.async_set_unique_id("nederlandse_spoorwegen")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Nederlandse Spoorwegen",
                    data={CONF_API_KEY: api_key},
                )
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"route": RouteSubentryFlowHandler}

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication step for updating API key."""
        errors: dict[str, str] = {}
        entry = self.context.get("entry")
        if entry is None and "entry_id" in self.context:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None and entry is not None:
            entry = cast(ConfigEntry, entry)
            api_key = user_input.get(CONF_API_KEY)
            if not api_key:
                errors[CONF_API_KEY] = "missing_fields"
            else:
                _LOGGER.debug("Reauth: User provided new API key for NS integration")
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reauth_successful")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="reauth",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration step for updating API key."""
        errors: dict[str, str] = {}
        entry = self.context.get("entry")
        if entry is None and "entry_id" in self.context:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None and entry is not None:
            entry = cast(ConfigEntry, entry)
            api_key = user_input.get(CONF_API_KEY)
            if not api_key:
                errors[CONF_API_KEY] = "missing_fields"
            else:
                _LOGGER.debug(
                    "Reconfigure: User provided new API key for NS integration"
                )
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reconfigure_successful")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )


class RouteSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying routes."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new route subentry."""
        return await self._async_step_route_form(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing route subentry."""
        return await self._async_step_route_form(user_input)

    async def _async_step_route_form(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the route configuration form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the route data
            try:
                await self._ensure_stations_available()
                station_options = await self._get_station_options()

                if not station_options:
                    errors["base"] = "no_stations_available"
                elif (
                    not user_input.get(CONF_NAME)
                    or not user_input.get(CONF_FROM)
                    or not user_input.get(CONF_TO)
                ):
                    errors["base"] = "missing_fields"
                elif user_input.get(CONF_FROM) == user_input.get(CONF_TO):
                    errors["base"] = "same_station"
                else:
                    # Validate stations exist (case-insensitive)
                    from_station = user_input.get(CONF_FROM)
                    to_station = user_input.get(CONF_TO)
                    via_station = user_input.get(CONF_VIA)

                    station_codes = [opt["value"] for opt in station_options]
                    # Create case-insensitive lookup
                    station_codes_upper = [code.upper() for code in station_codes]

                    if from_station and from_station.upper() not in station_codes_upper:
                        errors[CONF_FROM] = "invalid_station"
                    if to_station and to_station.upper() not in station_codes_upper:
                        errors[CONF_TO] = "invalid_station"
                    if via_station and via_station.upper() not in station_codes_upper:
                        errors[CONF_VIA] = "invalid_station"

                    if not errors:
                        # Create the route configuration - store codes in uppercase
                        route_config = {
                            CONF_NAME: user_input[CONF_NAME],
                            CONF_FROM: from_station.upper() if from_station else "",
                            CONF_TO: to_station.upper() if to_station else "",
                        }
                        if via_station:
                            route_config[CONF_VIA] = via_station.upper()
                        if user_input.get(CONF_TIME):
                            route_config[CONF_TIME] = user_input[CONF_TIME]

                        # Handle both creation and reconfiguration
                        if self.source == SOURCE_RECONFIGURE:
                            # For reconfiguration, update the existing subentry
                            return self.async_update_and_abort(
                                self._get_entry(),
                                self._get_reconfigure_subentry(),
                                data=route_config,
                                title=user_input[CONF_NAME],
                            )

                        # For new routes, create a new entry
                        return self.async_create_entry(
                            title=user_input[CONF_NAME], data=route_config
                        )

            except Exception:  # Allowed in config flows for robustness
                _LOGGER.exception("Exception in route subentry flow")
                errors["base"] = "unknown"

        # Show the form
        try:
            await self._ensure_stations_available()
            station_options = await self._get_station_options()

            if not station_options:
                errors["base"] = "no_stations_available"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({}),
                    errors=errors,
                )

            # Get current route data if reconfiguring
            current_route: dict[str, Any] = {}
            if self.source == "reconfigure":
                try:
                    subentry = self._get_reconfigure_subentry()
                    current_route = dict(subentry.data)
                except (ValueError, KeyError) as ex:
                    _LOGGER.warning(
                        "Failed to get subentry data for reconfigure: %s", ex
                    )

            route_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=current_route.get(CONF_NAME, "")
                    ): str,
                    vol.Required(
                        CONF_FROM, default=current_route.get(CONF_FROM, "")
                    ): selector({"select": {"options": station_options}}),
                    vol.Required(
                        CONF_TO, default=current_route.get(CONF_TO, "")
                    ): selector({"select": {"options": station_options}}),
                    vol.Optional(
                        CONF_VIA, default=current_route.get(CONF_VIA, "")
                    ): selector(
                        {
                            "select": {
                                "options": station_options,
                                "mode": "dropdown",
                                "custom_value": True,
                            }
                        }
                    ),
                    vol.Optional(
                        CONF_TIME, default=current_route.get(CONF_TIME, "")
                    ): str,
                }
            )

            return self.async_show_form(
                step_id="user",
                data_schema=route_schema,
                errors=errors,
            )

        except Exception:  # Allowed in config flows for robustness
            _LOGGER.exception("Exception creating route form")
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

    async def _ensure_stations_available(self) -> None:
        """Ensure stations are available in runtime_data, fetch if needed."""
        entry = self._get_entry()
        if (
            not hasattr(entry, "runtime_data")
            or not entry.runtime_data
            or not hasattr(entry.runtime_data, "stations")
            or not entry.runtime_data.stations
        ):
            # For tests or when runtime_data is not available, we can't fetch stations
            if not hasattr(entry, "runtime_data") or not entry.runtime_data:
                _LOGGER.debug("No runtime_data available, cannot fetch stations")
                return

            # Fetch stations using the coordinator's client
            coordinator = entry.runtime_data.coordinator
            try:
                stations = await self.hass.async_add_executor_job(
                    coordinator.client.get_stations
                )
                # Store in runtime_data
                entry.runtime_data.stations = stations
                entry.runtime_data.stations_updated = datetime.now(UTC).isoformat()
            except (ValueError, ConnectionError, TimeoutError) as ex:
                _LOGGER.warning("Failed to fetch stations for subentry flow: %s", ex)
            except (
                Exception  # noqa: BLE001  # Allowed in config flows for robustness
            ) as ex:
                _LOGGER.warning(
                    "Unexpected error fetching stations for subentry flow: %s", ex
                )

    async def _get_station_options(self) -> list[dict[str, str]]:
        """Get the list of station options for dropdowns, sorted by name."""
        entry = self._get_entry()
        stations = []
        if (
            hasattr(entry, "runtime_data")
            and entry.runtime_data
            and hasattr(entry.runtime_data, "stations")
            and entry.runtime_data.stations
        ):
            stations = entry.runtime_data.stations

        if not stations:
            return []

        # Build station mapping from fetched data
        station_mapping = self._build_station_mapping(stations)

        # Convert to dropdown options with station names as labels and codes as values
        station_options = [
            {"value": code, "label": name} for code, name in station_mapping.items()
        ]

        # Sort by label (station name)
        station_options.sort(key=lambda x: x["label"])
        return station_options

    def _build_station_mapping(self, stations: list) -> dict[str, str]:
        """Build a mapping of station codes to names from fetched station data."""
        station_mapping = {}

        for station in stations:
            code = None
            name = None

            if hasattr(station, "code") and hasattr(station, "name"):
                # Standard format: separate code and name attributes
                code = station.code
                name = station.name
            elif isinstance(station, dict):
                # Dict format
                code = station.get("code")
                name = station.get("name")
            else:
                # Handle string format or object with __str__ method
                station_str = str(station)

                # Remove class name wrapper if present (e.g., "<Station> AC Abcoude" -> "AC Abcoude")
                if station_str.startswith("<") and "> " in station_str:
                    station_str = station_str.split("> ", 1)[1]

                # Try to parse "CODE Name" format
                parts = station_str.strip().split(" ", 1)
                if (
                    len(parts) == 2 and len(parts[0]) <= 4 and parts[0].isupper()
                ):  # Station codes are typically 2-4 uppercase chars
                    code, name = parts
                else:
                    # If we can't parse it properly, skip this station
                    _LOGGER.debug("Could not parse station format: %s", station_str)
                    continue

            # Only add if we have both code and name
            if code and name:
                station_mapping[code.upper()] = name.strip()
            else:
                _LOGGER.debug("Skipping station with missing code or name: %s", station)

        return station_mapping
