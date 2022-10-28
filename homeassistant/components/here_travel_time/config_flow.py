"""Config flow for HERE Travel Time integration."""
from __future__ import annotations

import logging
from typing import Any

from herepy import HEREError, InvalidCredentialsError, RouteMode, RoutingApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    LocationSelector,
    TimeSelector,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DEFAULT_NAME,
    DOMAIN,
    IMPERIAL_UNITS,
    METRIC_UNITS,
    ROUTE_MODE_FASTEST,
    ROUTE_MODES,
    TRAFFIC_MODE_ENABLED,
    TRAFFIC_MODES,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODES,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)


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


def default_options(hass: HomeAssistant) -> dict[str, str | None]:
    """Get the default options."""
    default = {
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_ARRIVAL_TIME: None,
        CONF_DEPARTURE_TIME: None,
        CONF_UNIT_SYSTEM: METRIC_UNITS,
    }
    if hass.config.units is US_CUSTOMARY_SYSTEM:
        default[CONF_UNIT_SYSTEM] = IMPERIAL_UNITS
    return default


class HERETravelTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HERE Travel Time."""

    VERSION = 1

    def __init__(self) -> None:
        """Init Config Flow."""
        self._config: dict[str, Any] = {}

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
            try:
                await self.hass.async_add_executor_job(
                    validate_api_key, user_input[CONF_API_KEY]
                )
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except HEREError as error:
                _LOGGER.exception("Unexpected exception: %s", error)
                errors["base"] = "unknown"
            if not errors:
                self._config = user_input
                return self.async_show_menu(
                    step_id="origin_menu",
                    menu_options=["origin_coordinates", "origin_entity"],
                )
        return self.async_show_form(
            step_id="user", data_schema=get_user_step_schema(user_input), errors=errors
        )

    async def async_step_origin_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure origin by using gps coordinates."""
        if user_input is not None:
            self._config[CONF_ORIGIN_LATITUDE] = user_input[CONF_ORIGIN][CONF_LATITUDE]
            self._config[CONF_ORIGIN_LONGITUDE] = user_input[CONF_ORIGIN][
                CONF_LONGITUDE
            ]
            return self.async_show_menu(
                step_id="destination_menu",
                menu_options=["destination_coordinates", "destination_entity"],
            )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ORIGIN,
                    default={
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                ): LocationSelector()
            }
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
        schema = vol.Schema({vol.Required(CONF_ORIGIN_ENTITY_ID): EntitySelector()})
        return self.async_show_form(step_id="origin_entity", data_schema=schema)

    async def async_step_destination_coordinates(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure destination by using gps coordinates."""
        if user_input is not None:
            self._config[CONF_DESTINATION_LATITUDE] = user_input[CONF_DESTINATION][
                CONF_LATITUDE
            ]
            self._config[CONF_DESTINATION_LONGITUDE] = user_input[CONF_DESTINATION][
                CONF_LONGITUDE
            ]
            return self.async_create_entry(
                title=self._config[CONF_NAME],
                data=self._config,
                options=default_options(self.hass),
            )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DESTINATION,
                    default={
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                ): LocationSelector()
            }
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
                title=self._config[CONF_NAME],
                data=self._config,
                options=default_options(self.hass),
            )
        schema = vol.Schema(
            {vol.Required(CONF_DESTINATION_ENTITY_ID): EntitySelector()}
        )
        return self.async_show_form(step_id="destination_entity", data_schema=schema)


class HERETravelTimeOptionsFlow(config_entries.OptionsFlow):
    """Handle HERE Travel Time options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize HERE Travel Time options flow."""
        self.config_entry = config_entry
        self._config: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the HERE Travel Time options."""
        if user_input is not None:
            self._config = user_input
            if self.config_entry.data[CONF_MODE] == TRAVEL_MODE_PUBLIC_TIME_TABLE:
                return self.async_show_menu(
                    step_id="time_menu",
                    menu_options=["departure_time", "arrival_time", "no_time"],
                )
            return self.async_show_menu(
                step_id="time_menu",
                menu_options=["departure_time", "no_time"],
            )

        defaults = default_options(self.hass)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRAFFIC_MODE,
                    default=self.config_entry.options.get(
                        CONF_TRAFFIC_MODE, defaults[CONF_TRAFFIC_MODE]
                    ),
                ): vol.In(TRAFFIC_MODES),
                vol.Optional(
                    CONF_ROUTE_MODE,
                    default=self.config_entry.options.get(
                        CONF_ROUTE_MODE, defaults[CONF_ROUTE_MODE]
                    ),
                ): vol.In(ROUTE_MODES),
                vol.Optional(
                    CONF_UNIT_SYSTEM,
                    default=self.config_entry.options.get(
                        CONF_UNIT_SYSTEM, defaults[CONF_UNIT_SYSTEM]
                    ),
                ): vol.In(UNITS),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_no_time(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create Options Entry."""
        return self.async_create_entry(title="", data=self._config)

    async def async_step_arrival_time(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure arrival time."""
        if user_input is not None:
            self._config[CONF_ARRIVAL_TIME] = user_input[CONF_ARRIVAL_TIME]
            return self.async_create_entry(title="", data=self._config)

        schema = vol.Schema(
            {vol.Required(CONF_ARRIVAL_TIME, default="00:00:00"): TimeSelector()}
        )

        return self.async_show_form(step_id="arrival_time", data_schema=schema)

    async def async_step_departure_time(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure departure time."""
        if user_input is not None:
            self._config[CONF_DEPARTURE_TIME] = user_input[CONF_DEPARTURE_TIME]
            return self.async_create_entry(title="", data=self._config)

        schema = vol.Schema(
            {vol.Required(CONF_DEPARTURE_TIME, default="00:00:00"): TimeSelector()}
        )

        return self.async_show_form(step_id="departure_time", data_schema=schema)
