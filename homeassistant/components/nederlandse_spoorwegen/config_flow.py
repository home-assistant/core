"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .api import NSAPIAuthError, NSAPIConnectionError, NSAPIError, NSAPIWrapper
from .const import CONF_FROM, CONF_NAME, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN
from .utils import get_current_utc_timestamp, normalize_and_validate_time_format

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen.

    This config flow supports:
    - Initial setup with API key validation
    - Route management via subentries
    """

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            api_wrapper = NSAPIWrapper(self.hass, api_key)
            try:
                await api_wrapper.validate_api_key()
            except NSAPIAuthError:
                errors["base"] = "invalid_auth"
            except NSAPIConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # Allowed in config flows for robustness  # noqa: BLE001
                errors["base"] = "cannot_connect"
            if not errors:
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


class RouteSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying routes.

    This subentry flow supports:
    - Adding new routes with station selection
    - Editing existing routes
    - Validation of route configuration (stations, time format)
    - Station lookup and validation against NS API
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new route subentry."""
        return await self._async_step_route_form(user_input)

    async def _async_step_route_form(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the route configuration form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._validate_route_input(user_input)

            if not errors:
                route_config = self._create_route_config(user_input)
                return await self._handle_route_creation_or_update(
                    route_config, user_input[CONF_NAME]
                )

        return await self._show_route_configuration_form(errors)

    async def _validate_route_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate route input and return errors."""
        errors: dict[str, str] = {}

        try:
            await self._ensure_stations_available()
            station_options = await self._get_station_options()

            if not station_options:
                errors["base"] = "no_stations_available"
                return errors

            # Field validation
            if (
                not user_input.get(CONF_NAME)
                or not user_input.get(CONF_FROM)
                or not user_input.get(CONF_TO)
            ):
                errors["base"] = "missing_fields"
                return errors

            if user_input.get(CONF_FROM) == user_input.get(CONF_TO):
                errors["base"] = "same_station"
                return errors

            # Time validation
            if user_input.get(CONF_TIME):
                time_valid, _ = normalize_and_validate_time_format(
                    user_input[CONF_TIME]
                )
                if not time_valid:
                    errors[CONF_TIME] = "invalid_time_format"
                    return errors

            # Station validation
            entry = self._get_entry()
            if (
                hasattr(entry, "runtime_data")
                and entry.runtime_data
                and hasattr(entry.runtime_data, "stations")
                and entry.runtime_data.stations
            ):
                api_wrapper = NSAPIWrapper(self.hass, entry.data[CONF_API_KEY])
                valid_station_codes = api_wrapper.get_station_codes(
                    entry.runtime_data.stations
                )

                for field, station in (
                    (CONF_FROM, user_input.get(CONF_FROM)),
                    (CONF_TO, user_input.get(CONF_TO)),
                    (CONF_VIA, user_input.get(CONF_VIA)),
                ):
                    if (
                        station
                        and api_wrapper.normalize_station_code(station)
                        not in valid_station_codes
                    ):
                        errors[field] = "invalid_station"

        except Exception:  # Allowed in config flows for robustness
            _LOGGER.exception("Exception in route subentry flow")
            errors["base"] = "unknown"

        return errors

    def _create_route_config(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Create route configuration from user input."""
        from_station = user_input.get(CONF_FROM, "")
        to_station = user_input.get(CONF_TO, "")
        via_station = user_input.get(CONF_VIA)

        # Use centralized station code normalization
        entry = self._get_entry()
        api_wrapper = NSAPIWrapper(self.hass, entry.data[CONF_API_KEY])
        route_config = {
            CONF_NAME: user_input[CONF_NAME],
            CONF_FROM: api_wrapper.normalize_station_code(from_station),
            CONF_TO: api_wrapper.normalize_station_code(to_station),
        }

        if via_station:
            route_config[CONF_VIA] = api_wrapper.normalize_station_code(via_station)

        if user_input.get(CONF_TIME):
            _, normalized_time = normalize_and_validate_time_format(
                user_input[CONF_TIME]
            )
            if normalized_time:
                route_config[CONF_TIME] = normalized_time

        return route_config

    async def _handle_route_creation_or_update(
        self, route_config: dict[str, Any], route_name: str
    ) -> SubentryFlowResult:
        """Handle route creation."""
        return self.async_create_entry(title=route_name, data=route_config)

    async def _show_route_configuration_form(
        self, errors: dict[str, str]
    ) -> SubentryFlowResult:
        """Show the route configuration form."""
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
            title_key = "Add route"
            if self.source == "reconfigure":
                title_key = "Edit route"
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
                description_placeholders={"title": title_key},
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

            # Fetch stations using the API wrapper
            api_wrapper = NSAPIWrapper(self.hass, entry.data[CONF_API_KEY])
            try:
                stations = await api_wrapper.get_stations()
                entry.runtime_data.stations = stations
                entry.runtime_data.stations_updated = get_current_utc_timestamp()
            except (NSAPIAuthError, NSAPIConnectionError, NSAPIError) as ex:
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
        if (
            not hasattr(entry, "runtime_data")
            or not entry.runtime_data
            or not hasattr(entry.runtime_data, "stations")
            or not entry.runtime_data.stations
        ):
            return []

        # Use centralized station mapping from API wrapper
        api_wrapper = NSAPIWrapper(self.hass, entry.data[CONF_API_KEY])
        station_mapping = api_wrapper.build_station_mapping(entry.runtime_data.stations)

        # Convert to dropdown options with station names as labels and codes as values
        station_options = [
            {"value": code, "label": name} for code, name in station_mapping.items()
        ]

        # Sort by label (station name)
        station_options.sort(key=lambda x: x["label"])
        return station_options
