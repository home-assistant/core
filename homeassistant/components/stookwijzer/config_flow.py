"""Config flow to configure the Stookwijzer integration."""

from __future__ import annotations

from typing import Any

from stookwijzer import Stookwijzer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN


class StookwijzerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Stookwijzer."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            latitude, longitude = await Stookwijzer.async_transform_coordinates(
                async_get_clientsession(self.hass),
                user_input[CONF_LOCATION][CONF_LATITUDE],
                user_input[CONF_LOCATION][CONF_LONGITUDE],
            )
            if latitude and longitude:
                return self.async_create_entry(
                    title="Stookwijzer",
                    data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
                )
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default={
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ): LocationSelector()
                }
            ),
        )
