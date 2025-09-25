"""Config flow for Meteo.lt integration."""

from __future__ import annotations

import logging
from typing import Any

from meteo_lt import MeteoLtAPI, Place
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.util.location import distance

from .const import CONF_PLACE_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeteoLtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meteo.lt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api = MeteoLtAPI()
        self._places: list[Place] = []
        self._selected_place: Place | None = None
        self._user_coordinates: tuple[float, float] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the method selection step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["coordinates", "manual"],
        )

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the coordinates input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                latitude = user_input[CONF_LATITUDE]
                longitude = user_input[CONF_LONGITUDE]

                self._user_coordinates = (latitude, longitude)
                return await self.async_step_location_from_coordinates()
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.error("Error processing coordinates input: %s", err)
                errors["base"] = "unknown"

        # Get default coords from Home Assistant config
        home_coords = self._get_home_coordinates()
        default_lat = home_coords[0] if home_coords else None
        default_lon = home_coords[1] if home_coords else None

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=default_lat): vol.Coerce(float),
                vol.Required(CONF_LONGITUDE, default=default_lon): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="coordinates",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_location_from_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the location confirmation from coordinates step."""
        if not self._user_coordinates:
            return await self.async_step_coordinates()

        try:
            self._selected_place = await self._api.get_nearest_place(
                self._user_coordinates[0], self._user_coordinates[1]
            )
            place_distance = distance(
                self._user_coordinates[0],
                self._user_coordinates[1],
                self._selected_place.latitude,
                self._selected_place.longitude,
            )  # returns meters
            if place_distance is not None:
                place_distance = place_distance / 1000
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error finding nearest place: %s", err)
            return self.async_show_form(
                step_id="location_from_coordinates",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )

        if not self._selected_place:
            return self.async_show_form(
                step_id="location_from_coordinates",
                data_schema=vol.Schema({}),
                errors={"base": "no_location_found"},
            )

        return self.async_show_menu(
            step_id="location_from_coordinates",
            menu_options=["use_location", "find_manual"],
            description_placeholders={
                "location_name": self._selected_place.name,
                "distance": f"{place_distance:.1f}",
            },
        )

    async def async_step_use_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use the found location."""
        return await self._create_config_entry()

    async def async_step_find_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Go to manual location selection."""
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual location selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            place_code = user_input[CONF_PLACE_CODE]
            self._selected_place = next(
                (place for place in self._places if place.code == place_code),
                None,
            )
            if self._selected_place:
                return await self._create_config_entry()
            errors["base"] = "invalid_location"

        if not self._places:
            try:
                await self._api.fetch_places()
                self._places = self._api.places
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Error fetching places: %s", err)
                errors["base"] = "cannot_connect"

        if not self._places:
            return self.async_abort(reason="no_places_found")

        places_options = {
            place.code: f"{place.name} ({place.administrative_division})"
            for place in self._places
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PLACE_CODE): vol.In(places_options),
            }
        )

        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors,
        )

    def _get_home_coordinates(self) -> tuple[float, float] | None:
        """Get Home Assistant's configured home coordinates."""
        if (
            self.hass.config.latitude is not None
            and self.hass.config.longitude is not None
        ):
            return (self.hass.config.latitude, self.hass.config.longitude)
        return None

    async def _create_config_entry(self) -> ConfigFlowResult:
        """Create config entry with selected place."""
        if not self._selected_place:
            return await self.async_step_user()

        await self.async_set_unique_id(self._selected_place.code)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._selected_place.name,
            data={
                CONF_PLACE_CODE: self._selected_place.code,
            },
        )
