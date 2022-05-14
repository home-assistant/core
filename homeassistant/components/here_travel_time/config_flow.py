"""Config flow for HERE Travel Time integration."""
from __future__ import annotations

import logging
from typing import Any

from herepy import InvalidCredentialsError, RouteMode, RoutingApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_MODE, CONF_NAME, CONF_UNIT_SYSTEM
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import EntitySelector, LocationSelector, selector

from .const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL,
    CONF_DEPARTURE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_ROUTE_MODE,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODE,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    ROUTE_MODE_FASTEST,
    ROUTE_MODES,
    TIME_TYPES,
    TRAFFIC_MODE_DISABLED,
    TRAFFIC_MODE_ENABLED,
    TRAFFIC_MODES,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODES,
    UNITS,
)
from .sensor import (
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
)

_LOGGER = logging.getLogger(__name__)


def is_dupe_import(
    entry: config_entries.ConfigEntry,
    user_input: dict[str, Any],
    options: dict[str, Any],
) -> bool:
    """Return whether imported config already exists."""
    # Check the main data keys
    if any(
        user_input[key] != entry.data[key]
        for key in (CONF_API_KEY, CONF_MODE, CONF_NAME)
    ):
        return False

    # Check origin
    for key in (
        CONF_DESTINATION,
        CONF_ORIGIN,
        CONF_DESTINATION_ENTITY_ID,
        CONF_ORIGIN_ENTITY_ID,
    ):
        if user_input.get(key) != entry.data.get(key):
            return False

    # We have to check for options that don't have defaults
    for key in (
        CONF_TRAFFIC_MODE,
        CONF_UNIT_SYSTEM,
        CONF_ROUTE_MODE,
        CONF_TIME_TYPE,
        CONF_TIME,
    ):
        if options.get(key) != entry.options.get(key):
            return False

    return True


def validate_api_key(api_key: str) -> None:
    """Validate the user input allows us to connect."""
    known_working_origin = [38.9, -77.04833]
    known_working_destination = [39.0, -77.1]
    RoutingApi(api_key).public_transport_timetable(
        known_working_origin,
        known_working_destination,
        True,
        [
            RouteMode[ROUTE_MODE_FASTEST],
            RouteMode[TRAVEL_MODE_CAR],
            RouteMode[TRAFFIC_MODE_ENABLED],
        ],
        arrival=None,
        departure="now",
    )


def get_user_step_schema(data: dict[str, Any]) -> vol.Schema:
    """Get a populated schema or default."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME, default=data.get(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
            vol.Required(CONF_API_KEY, default=data.get(CONF_API_KEY)): cv.string,
            vol.Optional(
                CONF_MODE, default=data.get(CONF_MODE, TRAVEL_MODE_CAR)
            ): vol.In(TRAVEL_MODES),
        }
    )


class HERETravelTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HERE Travel Time."""

    VERSION = 1

    _config: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HERETravelTimeOptionsFlow:
        """Get the options flow."""
        return HERETravelTimeOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}
        if user_input:
            if self.source == config_entries.SOURCE_IMPORT:
                return await self.async_import(user_input)
            try:
                await self.hass.async_add_executor_job(
                    validate_api_key, user_input[CONF_API_KEY]
                )
                self._config = user_input
                return self.async_show_menu(
                    step_id="origin_menu",
                    menu_options=["origin_coordinates", "origin_entity"],
                )
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", error)
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="user", data_schema=get_user_step_schema(user_input), errors=errors
        )

    async def async_step_origin_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure origin by using gps coordinates."""
        if user_input is not None:
            self._config[
                CONF_ORIGIN
            ] = f"{user_input[CONF_ORIGIN]['latitude']},{user_input[CONF_ORIGIN]['longitude']}"
            return self.async_show_menu(
                step_id="destination_menu",
                menu_options=["destination_coordinates", "destination_entity"],
            )
        schema = vol.Schema(
            {CONF_ORIGIN: selector({LocationSelector.selector_type: {}})}
        )
        return self.async_show_form(step_id="origin_coordinates", data_schema=schema)

    async def async_step_origin_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure origin by using an entity."""
        if user_input is not None:
            self._config[CONF_ORIGIN_ENTITY_ID] = user_input[CONF_ORIGIN_ENTITY_ID]
            return self.async_show_menu(
                step_id="destination_menu",
                menu_options=["destination_coordinates", "destination_entity"],
            )
        schema = vol.Schema(
            {CONF_ORIGIN_ENTITY_ID: selector({EntitySelector.selector_type: {}})}
        )
        return self.async_show_form(step_id="origin_entity", data_schema=schema)

    async def async_step_destination_coordinates(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure destination by using gps coordinates."""
        if user_input is not None:
            self._config[
                CONF_DESTINATION
            ] = f"{user_input[CONF_DESTINATION]['latitude']},{user_input[CONF_DESTINATION]['longitude']}"
            return self.async_create_entry(
                title=self._config[CONF_NAME], data=self._config
            )
        schema = vol.Schema(
            {CONF_DESTINATION: selector({LocationSelector.selector_type: {}})}
        )
        return self.async_show_form(
            step_id="destination_coordinates", data_schema=schema
        )

    async def async_step_destination_entity(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure destination by using an entity."""
        if user_input is not None:
            self._config[CONF_DESTINATION_ENTITY_ID] = user_input[
                CONF_DESTINATION_ENTITY_ID
            ]
            return self.async_create_entry(
                title=self._config[CONF_NAME], data=self._config
            )
        schema = vol.Schema(
            {CONF_DESTINATION_ENTITY_ID: selector({EntitySelector.selector_type: {}})}
        )
        return self.async_show_form(step_id="destination_entity", data_schema=schema)

    async_step_import = async_step_user

    async def async_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import from configuration.yaml."""
        options: dict[str, Any] = {}
        user_input, options = self._transform_import_input(user_input)
        # We need to prevent duplicate imports
        if any(
            is_dupe_import(entry, user_input, options)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.source == config_entries.SOURCE_IMPORT
        ):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=user_input[CONF_NAME], data=user_input, options=options
        )

    def _transform_import_input(
        self, user_input
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Transform platform schema input to new model."""
        options: dict[str, Any] = {}
        if user_input.get(CONF_ORIGIN_LATITUDE) is not None:
            user_input[
                CONF_ORIGIN
            ] = f"{user_input.pop(CONF_ORIGIN_LATITUDE)},{user_input.pop(CONF_ORIGIN_LONGITUDE)}"
        else:
            user_input[CONF_ORIGIN_ENTITY_ID] = user_input.pop(CONF_ORIGIN_ENTITY_ID)

        if user_input.get(CONF_DESTINATION_LATITUDE) is not None:
            user_input[
                CONF_DESTINATION
            ] = f"{user_input.pop(CONF_DESTINATION_LATITUDE)},{user_input.pop(CONF_DESTINATION_LONGITUDE)}"
        else:
            user_input[CONF_DESTINATION_ENTITY_ID] = user_input.pop(
                CONF_DESTINATION_ENTITY_ID
            )

        options[CONF_TRAFFIC_MODE] = (
            TRAFFIC_MODE_ENABLED
            if user_input.pop(CONF_TRAFFIC_MODE, False)
            else TRAFFIC_MODE_DISABLED
        )
        options[CONF_ROUTE_MODE] = user_input.pop(CONF_ROUTE_MODE)
        options[CONF_UNIT_SYSTEM] = user_input.pop(
            CONF_UNIT_SYSTEM, self.hass.config.units.name
        )
        options[CONF_TIME_TYPE] = (
            ARRIVAL_TIME if CONF_ARRIVAL in user_input else DEPARTURE_TIME
        )
        options[CONF_TIME] = None
        if (arrival_time := user_input.pop(CONF_ARRIVAL, None)) is not None:
            options[CONF_TIME] = arrival_time
        if (departure_time := user_input.pop(CONF_DEPARTURE, None)) is not None:
            options[CONF_TIME] = departure_time

        return user_input, options


class HERETravelTimeOptionsFlow(config_entries.OptionsFlow):
    """Handle HERE Travel Time options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize HERE Travel Time options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the HERE Travel Time options."""
        errors = {}

        def convert_time(user_input: dict[str, Any]) -> None:
            """Validate time since cv.time cannot be used in schema or stored in entity config."""
            if user_input[CONF_TIME] != "":
                try:
                    cv.time(user_input[CONF_TIME])
                except vol.Invalid:
                    errors["base"] = "invalid_time"
            else:
                user_input[CONF_TIME] = None

        if user_input is not None:
            convert_time(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        default_time = self.config_entry.options.get(CONF_TIME, "")
        if default_time is None:  # Convert None to empty string so cv.string passes
            default_time = ""

        options = {
            vol.Optional(
                CONF_TRAFFIC_MODE,
                default=self.config_entry.options.get(
                    CONF_TRAFFIC_MODE, TRAFFIC_MODE_ENABLED
                ),
            ): vol.In(TRAFFIC_MODES),
            vol.Optional(
                CONF_ROUTE_MODE,
                default=self.config_entry.options.get(
                    CONF_ROUTE_MODE, ROUTE_MODE_FASTEST
                ),
            ): vol.In(ROUTE_MODES),
            vol.Optional(
                CONF_UNIT_SYSTEM,
                default=self.config_entry.options.get(
                    CONF_UNIT_SYSTEM, self.hass.config.units.name
                ),
            ): vol.In(UNITS),
            vol.Optional(CONF_TIME, default=default_time): cv.string,
        }
        # Arrival is only allowed for publicTransportTimeTable
        if self.config_entry.data[CONF_MODE] == TRAVEL_MODE_PUBLIC_TIME_TABLE:
            options[vol.Optional(CONF_TIME_TYPE, default=DEPARTURE_TIME)] = vol.In(
                TIME_TYPES
            )
        else:
            options[vol.Optional(CONF_TIME_TYPE, default=DEPARTURE_TIME)] = vol.In(
                [DEPARTURE_TIME]
            )

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
