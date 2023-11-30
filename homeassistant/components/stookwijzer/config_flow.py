"""Config flow to configure the Stookwijzer integration."""
from __future__ import annotations

from typing import Any

from stookwijzer import Stookwijzer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN


class StookwijzerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Stookwijzer."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            x, y = await Stookwijzer.async_transform_coordinates(
                session,
                user_input[CONF_LOCATION][CONF_LATITUDE],
                user_input[CONF_LOCATION][CONF_LONGITUDE],
            )

            if x and not y:
                return self.async_create_entry(
                    title="Stookwijzer",
                    data={CONF_LATITUDE: x, CONF_LONGITUDE: y},
                )

        return self.async_show_form(
            step_id="user",
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
