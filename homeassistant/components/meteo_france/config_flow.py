"""Config flow to configure the Meteo-France integration."""

from __future__ import annotations

import logging
from typing import Any

from meteofrance_api.client import MeteoFranceClient
from meteofrance_api.model import Place
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback

from .const import CONF_CITY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeteoFranceFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Meteo-France config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init MeteoFranceFlowHandler."""
        self.places: list[Place] = []

    @callback
    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY, default=user_input.get(CONF_CITY, "")): str}
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        city = user_input[CONF_CITY]  # Might be a city name or a postal code
        latitude = user_input.get(CONF_LATITUDE)
        longitude = user_input.get(CONF_LONGITUDE)

        if not latitude:
            client = MeteoFranceClient()
            self.places = await self.hass.async_add_executor_job(
                client.search_places, city
            )
            _LOGGER.debug("Places search result: %s", self.places)
            if not self.places:
                errors[CONF_CITY] = "empty"
                return self._show_setup_form(user_input, errors)

            return await self.async_step_cities()

        # Check if already configured
        await self.async_set_unique_id(f"{latitude}, {longitude}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=city,
            data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
        )

    async def async_step_cities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step where the user choose the city from the API search results."""
        if not user_input:
            if len(self.places) > 1 and self.source != SOURCE_IMPORT:
                places_for_form: dict[str, str] = {}
                for place in self.places:
                    places_for_form[_build_place_key(place)] = f"{place}"

                return self.async_show_form(
                    step_id="cities",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_CITY): vol.All(
                                vol.Coerce(str), vol.In(places_for_form)
                            )
                        }
                    ),
                )
            user_input = {CONF_CITY: _build_place_key(self.places[0])}

        city_infos = user_input[CONF_CITY].split(";")
        return await self.async_step_user(
            {
                CONF_CITY: city_infos[0],
                CONF_LATITUDE: city_infos[1],
                CONF_LONGITUDE: city_infos[2],
            }
        )


def _build_place_key(place: Place) -> str:
    return f"{place};{place.latitude};{place.longitude}"
