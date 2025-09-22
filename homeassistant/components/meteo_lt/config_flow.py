"""Config flow for Meteo.lt integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .api import MeteoLtApi, MeteoLtApiError
from .const import CONF_PLACE_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeteoLtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meteo.lt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._places: dict[str, str] = {}
        self._selected_place_code: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_place_code = user_input[CONF_PLACE_CODE]
            place_name = self._places[self._selected_place_code]
            custom_name = user_input.get(CONF_NAME, place_name)

            # Check for existing entries with the same place code
            await self.async_set_unique_id(self._selected_place_code)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=custom_name,
                data={
                    CONF_PLACE_CODE: self._selected_place_code,
                    CONF_NAME: custom_name,
                },
            )

        # Fetch available places
        api = MeteoLtApi(self.hass)
        try:
            places = await api.get_places()
            self._places = {place.code: place.name for place in places}
        except MeteoLtApiError:
            errors["base"] = "cannot_connect"

        if not self._places:
            return self.async_abort(reason="no_places_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PLACE_CODE): vol.In(self._places),
                vol.Optional(CONF_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
