"""Config flow for HERE Travel Time integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from here_routing import (
    HERERoutingApi,
    HERERoutingError,
    HERERoutingUnauthorizedError,
    Place,
    TransportMode,
)
from here_transit import HERETransitError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    LocationSelector,
    TimeSelector,
)

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
    DEFAULT_NAME,
    DOMAIN,
    ROUTE_MODE_FASTEST,
    ROUTE_MODES,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {
    CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
    CONF_ARRIVAL_TIME: None,
    CONF_DEPARTURE_TIME: None,
}


async def async_validate_api_key(api_key: str) -> None:
    """Validate the user input allows us to connect."""
    known_working_origin = Place(latitude=38.9, longitude=-77.04833)
    known_working_destination = Place(latitude=39.0, longitude=-77.1)

    await HERERoutingApi(api_key).route(
        origin=known_working_origin,
        destination=known_working_destination,
        transport_mode=TransportMode.CAR,
    )


def get_user_step_schema(data: Mapping[str, Any]) -> vol.Schema:
    """Get a populated schema or default."""
    travel_mode = data.get(CONF_MODE, TRAVEL_MODE_CAR)
    if travel_mode == "publicTransportTimeTable":
        travel_mode = TRAVEL_MODE_PUBLIC
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


class HERETravelTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HERE Travel Time."""

    VERSION = 1

    def __init__(self) -> None:
        """Init Config Flow."""
        self._config: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HERETravelTimeOptionsFlow:
        """Get the options flow."""
        return HERETravelTimeOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}
        if user_input:
            try:
                await async_validate_api_key(user_input[CONF_API_KEY])
            except HERERoutingUnauthorizedError:
                errors["base"] = "invalid_auth"
            except (HERERoutingError, HERETransitError):
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if not errors:
                self._config[CONF_NAME] = user_input[CONF_NAME]
                self._config[CONF_API_KEY] = user_input[CONF_API_KEY]
                self._config[CONF_MODE] = user_input[CONF_MODE]
                return await self.async_step_origin_menu()
        return self.async_show_form(
            step_id="user", data_schema=get_user_step_schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return self.async_show_form(
            step_id="user",
            data_schema=get_user_step_schema(self._get_reconfigure_entry().data),
        )

    async def async_step_origin_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the origin menu."""
        return self.async_show_menu(
            step_id="origin_menu",
            menu_options=["origin_coordinates", "origin_entity"],
        )

    async def async_step_origin_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure origin by using gps coordinates."""
        if user_input is not None:
            self._config[CONF_ORIGIN_LATITUDE] = user_input[CONF_ORIGIN][CONF_LATITUDE]
            self._config[CONF_ORIGIN_LONGITUDE] = user_input[CONF_ORIGIN][
                CONF_LONGITUDE
            ]
            # Remove possible previous configuration using an entity_id
            self._config.pop(CONF_ORIGIN_ENTITY_ID, None)
            return await self.async_step_destination_menu()
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_ORIGIN,
                    ): LocationSelector()
                }
            ),
            {
                CONF_ORIGIN: {
                    CONF_LATITUDE: self._config.get(CONF_ORIGIN_LATITUDE)
                    or self.hass.config.latitude,
                    CONF_LONGITUDE: self._config.get(CONF_ORIGIN_LONGITUDE)
                    or self.hass.config.longitude,
                }
            },
        )
        return self.async_show_form(step_id="origin_coordinates", data_schema=schema)

    async def async_step_origin_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure origin by using an entity."""
        if user_input is not None:
            self._config[CONF_ORIGIN_ENTITY_ID] = user_input[CONF_ORIGIN_ENTITY_ID]
            # Remove possible previous configuration using coordinates
            self._config.pop(CONF_ORIGIN_LATITUDE, None)
            self._config.pop(CONF_ORIGIN_LONGITUDE, None)
            return await self.async_step_destination_menu()
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_ORIGIN_ENTITY_ID,
                    ): EntitySelector()
                }
            ),
            {CONF_ORIGIN_ENTITY_ID: self._config.get(CONF_ORIGIN_ENTITY_ID)},
        )
        return self.async_show_form(step_id="origin_entity", data_schema=schema)

    async def async_step_destination_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the destination menu."""
        return self.async_show_menu(
            step_id="destination_menu",
            menu_options=["destination_coordinates", "destination_entity"],
        )

    async def async_step_destination_coordinates(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure destination by using gps coordinates."""
        if user_input is not None:
            self._config[CONF_DESTINATION_LATITUDE] = user_input[CONF_DESTINATION][
                CONF_LATITUDE
            ]
            self._config[CONF_DESTINATION_LONGITUDE] = user_input[CONF_DESTINATION][
                CONF_LONGITUDE
            ]
            # Remove possible previous configuration using an entity_id
            self._config.pop(CONF_DESTINATION_ENTITY_ID, None)
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=self._config[CONF_NAME],
                    data=self._config,
                )
            return self.async_create_entry(
                title=self._config[CONF_NAME],
                data=self._config,
                options=DEFAULT_OPTIONS,
            )
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_DESTINATION,
                    ): LocationSelector()
                }
            ),
            {
                CONF_DESTINATION: {
                    CONF_LATITUDE: self._config.get(CONF_DESTINATION_LATITUDE)
                    or self.hass.config.latitude,
                    CONF_LONGITUDE: self._config.get(CONF_DESTINATION_LONGITUDE)
                    or self.hass.config.longitude,
                },
            },
        )
        return self.async_show_form(
            step_id="destination_coordinates", data_schema=schema
        )

    async def async_step_destination_entity(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure destination by using an entity."""
        if user_input is not None:
            self._config[CONF_DESTINATION_ENTITY_ID] = user_input[
                CONF_DESTINATION_ENTITY_ID
            ]
            # Remove possible previous configuration using coordinates
            self._config.pop(CONF_DESTINATION_LATITUDE, None)
            self._config.pop(CONF_DESTINATION_LONGITUDE, None)
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data=self._config
                )
            return self.async_create_entry(
                title=self._config[CONF_NAME],
                data=self._config,
                options=DEFAULT_OPTIONS,
            )
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_DESTINATION_ENTITY_ID,
                    ): EntitySelector()
                }
            ),
            {CONF_DESTINATION_ENTITY_ID: self._config.get(CONF_DESTINATION_ENTITY_ID)},
        )
        return self.async_show_form(step_id="destination_entity", data_schema=schema)


class HERETravelTimeOptionsFlow(OptionsFlow):
    """Handle HERE Travel Time options."""

    def __init__(self) -> None:
        """Initialize HERE Travel Time options flow."""
        self._config: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the HERE Travel Time options."""
        if user_input is not None:
            self._config = user_input
            return await self.async_step_time_menu()

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_ROUTE_MODE,
                        default=self.config_entry.options.get(
                            CONF_ROUTE_MODE, DEFAULT_OPTIONS[CONF_ROUTE_MODE]
                        ),
                    ): vol.In(ROUTE_MODES),
                }
            ),
            {
                CONF_ROUTE_MODE: self.config_entry.options.get(
                    CONF_ROUTE_MODE, DEFAULT_OPTIONS[CONF_ROUTE_MODE]
                ),
            },
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_time_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the time menu."""
        return self.async_show_menu(
            step_id="time_menu",
            menu_options=["departure_time", "arrival_time", "no_time"],
        )

    async def async_step_no_time(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create Options Entry."""
        return self.async_create_entry(title="", data=self._config)

    async def async_step_arrival_time(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure arrival time."""
        if user_input is not None:
            self._config[CONF_ARRIVAL_TIME] = user_input[CONF_ARRIVAL_TIME]
            return self.async_create_entry(title="", data=self._config)

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {vol.Required(CONF_ARRIVAL_TIME, default="00:00:00"): TimeSelector()}
            ),
            {CONF_ARRIVAL_TIME: "00:00:00"},
        )

        return self.async_show_form(step_id="arrival_time", data_schema=schema)

    async def async_step_departure_time(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure departure time."""
        if user_input is not None:
            self._config[CONF_DEPARTURE_TIME] = user_input[CONF_DEPARTURE_TIME]
            return self.async_create_entry(title="", data=self._config)

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {vol.Required(CONF_DEPARTURE_TIME, default="00:00:00"): TimeSelector()}
            ),
            {CONF_DEPARTURE_TIME: "00:00:00"},
        )

        return self.async_show_form(step_id="departure_time", data_schema=schema)
