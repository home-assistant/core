"""Adds config flow for GIOS."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from gios import ApiError, Gios, InvalidSensorsData, NoStationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_TIMEOUT, CONF_STATION_ID, DOMAIN


class GiosFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GIOS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                await self.async_set_unique_id(
                    str(user_input[CONF_STATION_ID]), raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                websession = async_get_clientsession(self.hass)

                async with timeout(API_TIMEOUT):
                    gios = Gios(user_input[CONF_STATION_ID], websession)
                    await gios.async_update()

                assert gios.station_name is not None
                return self.async_create_entry(
                    title=gios.station_name,
                    data=user_input,
                )
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except NoStationError:
                errors[CONF_STATION_ID] = "wrong_station_id"
            except InvalidSensorsData:
                errors[CONF_STATION_ID] = "invalid_sensors_data"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): int,
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                }
            ),
            errors=errors,
        )
