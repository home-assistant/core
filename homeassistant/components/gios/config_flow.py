"""Adds config flow for GIOS."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiohttp.client_exceptions import ClientConnectorError
from gios import ApiError, Gios, InvalidSensorsDataError, NoStationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import API_TIMEOUT, CONF_STATION_ID, DOMAIN


class GiosFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for GIOS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        websession = async_get_clientsession(self.hass)

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]

            try:
                await self.async_set_unique_id(station_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                async with asyncio.timeout(API_TIMEOUT):
                    gios = await Gios.create(websession, int(station_id))
                    await gios.async_update()

                # GIOS treats station ID as int
                user_input[CONF_STATION_ID] = int(station_id)

                if TYPE_CHECKING:
                    assert gios.station_name is not None

                return self.async_create_entry(
                    title=gios.station_name,
                    data=user_input,
                )
            except (ApiError, ClientConnectorError, TimeoutError):
                errors["base"] = "cannot_connect"
            except InvalidSensorsDataError:
                errors[CONF_STATION_ID] = "invalid_sensors_data"

        try:
            gios = await Gios.create(websession)
        except (ApiError, ClientConnectorError, NoStationError):
            return self.async_abort(reason="cannot_connect")

        options: list[SelectOptionDict] = [
            SelectOptionDict(value=str(station.id), label=station.name)
            for station in gios.measurement_stations.values()
        ]

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        sort=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(CONF_NAME, default=self.hass.config.location_name): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
