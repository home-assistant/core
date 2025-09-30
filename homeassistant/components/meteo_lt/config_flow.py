"""Config flow for Meteo.lt integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from meteo_lt import MeteoLtAPI, Place
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
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
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.error("Error fetching places: %s", err)
                return self.async_abort(reason="cannot_connect")

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
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

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
